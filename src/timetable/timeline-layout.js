const MINUTES_PER_DAY = 24 * 60;

export function timeToMinutes(value) {
  const match = /^(\d{2}):(\d{2})$/.exec(String(value || ""));
  if (!match) throw new Error(`Invalid timetable time: ${value}`);
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour === 24 && minute === 0) return MINUTES_PER_DAY;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    throw new Error(`Invalid timetable time: ${value}`);
  }
  return hour * 60 + minute;
}

function eventPriority(event) {
  return { assigned: 0, self: 1, background: 2 }[event.origin] ?? 9;
}

function finalizeOverlapGroup(group, groupIndex) {
  const laneEnds = [];
  for (const item of group) {
    let lane = laneEnds.findIndex((end) => end <= item.startMinute);
    if (lane < 0) lane = laneEnds.length;
    laneEnds[lane] = item.endMinute;
    item.lane = lane;
  }
  const laneCount = Math.max(1, laneEnds.length);
  return group.map((item) => ({
    ...item,
    laneCount,
    overlapGroup: groupIndex,
    isOverlapping: laneCount > 1,
  }));
}

export function layoutTimelineEvents(events) {
  const normalized = events.map((event, sourceIndex) => {
    const startMinute = timeToMinutes(event.start);
    const endMinute = timeToMinutes(event.end);
    if (startMinute < 0 || startMinute >= MINUTES_PER_DAY || endMinute <= startMinute || endMinute > MINUTES_PER_DAY) {
      throw new Error(`Invalid event window ${event.start}-${event.end}`);
    }
    return {
      event,
      sourceIndex,
      startMinute,
      endMinute,
      durationMinutes: endMinute - startMinute,
      lane: 0,
    };
  }).sort((left, right) => (
    left.startMinute - right.startMinute
    || eventPriority(left.event) - eventPriority(right.event)
    || right.endMinute - left.endMinute
    || left.sourceIndex - right.sourceIndex
  ));

  const result = [];
  let group = [];
  let groupEnd = -1;
  let groupIndex = 0;

  for (const item of normalized) {
    if (group.length && item.startMinute >= groupEnd) {
      result.push(...finalizeOverlapGroup(group, groupIndex));
      group = [];
      groupEnd = -1;
      groupIndex += 1;
    }
    group.push(item);
    groupEnd = Math.max(groupEnd, item.endMinute);
  }
  if (group.length) result.push(...finalizeOverlapGroup(group, groupIndex));

  return result.sort((left, right) => (
    left.startMinute - right.startMinute
    || left.lane - right.lane
    || left.sourceIndex - right.sourceIndex
  ));
}

export function buildTimelineProjection(layouts, options = {}) {
  const activeMinuteHeight = Math.max(0.01, Number(options.activeMinuteHeight) || 1);
  const idleMinuteHeight = Math.max(
    0.01,
    Math.min(activeMinuteHeight, Number(options.idleMinuteHeight) || activeMinuteHeight * 0.28),
  );
  const protectedRanges = Array.isArray(options.protectedRanges) ? options.protectedRanges : [];
  const normalizeRanges = (ranges) => ranges.map((range) => {
    const startMinute = Math.max(0, Math.min(MINUTES_PER_DAY, Number(range.startMinute) || 0));
    const endMinute = Math.max(startMinute, Math.min(MINUTES_PER_DAY, Number(range.endMinute) || 0));
    return { startMinute, endMinute };
  }).filter((range) => range.endMinute > range.startMinute)
    .sort((left, right) => left.startMinute - right.startMinute || left.endMinute - right.endMinute);

  const mergeRanges = (ranges) => {
    const merged = [];
    for (const range of normalizeRanges(ranges)) {
      const previous = merged.at(-1);
      if (!previous || range.startMinute > previous.endMinute) {
        merged.push({ ...range });
      } else {
        previous.endMinute = Math.max(previous.endMinute, range.endMinute);
      }
    }
    return merged;
  };

  const eventRanges = mergeRanges(layouts);
  const cardRanges = mergeRanges(protectedRanges);
  const activeRanges = mergeRanges([...eventRanges, ...cardRanges]);
  const rangeOverlap = (ranges, startMinute, endMinute) => ranges.reduce(
    (total, range) => total + Math.max(
      0,
      Math.min(endMinute, range.endMinute) - Math.max(startMinute, range.startMinute),
    ),
    0,
  );

  const segments = [];
  let minuteCursor = 0;
  let pixelCursor = 0;
  for (const range of activeRanges) {
    if (range.startMinute > minuteCursor) {
      const durationMinutes = range.startMinute - minuteCursor;
      const height = durationMinutes * idleMinuteHeight;
      segments.push({
        startMinute: minuteCursor,
        endMinute: range.startMinute,
        top: pixelCursor,
        height,
        minuteHeight: idleMinuteHeight,
        active: false,
      });
      pixelCursor += height;
    }
    const durationMinutes = range.endMinute - range.startMinute;
    const height = durationMinutes * activeMinuteHeight;
    segments.push({
      startMinute: range.startMinute,
      endMinute: range.endMinute,
      top: pixelCursor,
      height,
      minuteHeight: activeMinuteHeight,
      active: true,
    });
    pixelCursor += height;
    minuteCursor = range.endMinute;
  }
  if (minuteCursor < MINUTES_PER_DAY) {
    const durationMinutes = MINUTES_PER_DAY - minuteCursor;
    const height = durationMinutes * idleMinuteHeight;
    segments.push({
      startMinute: minuteCursor,
      endMinute: MINUTES_PER_DAY,
      top: pixelCursor,
      height,
      minuteHeight: idleMinuteHeight,
      active: false,
    });
    pixelCursor += height;
  }

  const projectMinute = (value) => {
    const minute = Math.max(0, Math.min(MINUTES_PER_DAY, Number(value) || 0));
    if (minute >= MINUTES_PER_DAY) return pixelCursor;
    const segment = segments.find((candidate) => (
      minute >= candidate.startMinute && minute < candidate.endMinute
    )) || segments.at(-1);
    return segment.top + (minute - segment.startMinute) * segment.minuteHeight;
  };

  const hourBands = Array.from({ length: 24 }, (_, hour) => {
    const startMinute = hour * 60;
    const endMinute = (hour + 1) * 60;
    const eventMinutes = rangeOverlap(eventRanges, startMinute, endMinute);
    const cardMinutes = rangeOverlap(cardRanges, startMinute, endMinute);
    const activeMinutes = rangeOverlap(activeRanges, startMinute, endMinute);
    const idleMinutes = 60 - activeMinutes;
    return {
      hour,
      startMinute,
      endMinute,
      top: projectMinute(startMinute),
      height: projectMinute(endMinute) - projectMinute(startMinute),
      activeMinutes,
      idleMinutes,
      active: idleMinutes <= 0.001,
      hasEvent: eventMinutes > 0.001,
      hasCard: cardMinutes > 0.001,
    };
  });

  const activeMinuteCount = activeRanges.reduce(
    (total, range) => total + range.endMinute - range.startMinute,
    0,
  );
  const compressedMinuteCount = MINUTES_PER_DAY - activeMinuteCount;

  return {
    activeMinuteHeight,
    idleMinuteHeight,
    segments,
    hourBands,
    activeMinuteCount,
    compressedMinuteCount,
    activeHourCount: hourBands.filter((band) => band.activeMinutes > 0.001).length,
    compressedHourCount: hourBands.filter((band) => band.idleMinutes > 0.001).length,
    fullyCompressedHourCount: hourBands.filter((band) => band.activeMinutes <= 0.001).length,
    partiallyCompressedHourCount: hourBands.filter((band) => (
      band.activeMinutes > 0.001 && band.idleMinutes > 0.001
    )).length,
    height: pixelCursor,
    projectMinute,
    projectSpan(startMinute, endMinute) {
      return projectMinute(endMinute) - projectMinute(startMinute);
    },
  };
}

export function positionTimelineElement(element, layout) {
  const laneWidth = 100 / layout.laneCount;
  element.dataset.start = layout.event.start;
  element.dataset.end = layout.event.end;
  element.dataset.lane = String(layout.lane);
  element.dataset.laneCount = String(layout.laneCount);
  element.dataset.overlapGroup = String(layout.overlapGroup);
  element.dataset.durationMinutes = String(layout.durationMinutes);
  element.style.setProperty("--event-start-minute", String(layout.startMinute));
  element.style.setProperty("--event-duration-minutes", String(layout.durationMinutes));
  element.style.setProperty("--event-lane", String(layout.lane));
  element.style.setProperty("--event-lane-count", String(layout.laneCount));
  element.style.left = `${layout.lane * laneWidth}%`;
  element.style.width = `calc(${laneWidth}% - 4px)`;
  element.classList.toggle("is-overlapping", layout.isOverlapping);
  element.classList.toggle("is-first-lane", layout.lane === 0);
  element.classList.toggle("is-last-lane", layout.lane === layout.laneCount - 1);
  element.classList.toggle("is-micro-event", layout.durationMinutes < 8);
  element.classList.toggle("is-compact-event", layout.durationMinutes >= 8 && layout.durationMinutes < 24);
  element.classList.toggle("is-medium-event", layout.durationMinutes >= 24 && layout.durationMinutes < 50);
  return element;
}

function readingRangesOverlap(left, right) {
  return left.column < right.column + right.columnSpan
    && right.column < left.column + left.columnSpan;
}

export function layoutTimelineReadingCards(items, options) {
  const columnCount = Math.max(1, Number(options.columnCount) || 1);
  const columnGap = Math.max(0, Number(options.columnGap) || 0);
  const rowGap = Math.max(0, Number(options.rowGap) || 0);
  const canvasWidth = Math.max(1, Number(options.canvasWidth) || 1);
  const canvasHeight = Math.max(1, Number(options.canvasHeight) || MINUTES_PER_DAY);
  const minuteHeight = Math.max(0.01, Number(options.minuteHeight) || 1);
  const edgePadding = Math.max(0, Number(options.edgePadding) || 0);
  const columnWidth = (canvasWidth - columnGap * (columnCount - 1)) / columnCount;
  const placed = [];

  for (const item of items) {
    const columnSpan = Math.max(1, Math.min(columnCount, Number(item.columnSpan) || 1));
    const maximumColumn = columnCount - columnSpan;
    const preferredColumn = Math.max(0, Math.min(maximumColumn, Number(item.preferredColumn) || 0));
    const height = Math.max(1, Number(item.height) || 1);
    const anchorMinute = Number.isFinite(Number(item.anchorMinute))
      ? Number(item.anchorMinute)
      : Number(item.startMinute);
    const anchorRatio = Math.max(0, Math.min(1, Number(item.anchorRatio) || 0));
    const anchorPosition = Number.isFinite(Number(item.anchorPosition))
      ? Number(item.anchorPosition)
      : anchorMinute * minuteHeight;
    const desiredTop = Math.max(
      edgePadding,
      Math.min(anchorPosition - height * anchorRatio, canvasHeight - height - edgePadding),
    );
    let best = null;

    const allowedColumns = Array.isArray(item.allowedColumns)
      ? [...new Set(item.allowedColumns.map(Number))]
        .filter((column) => Number.isInteger(column) && column >= 0 && column <= maximumColumn)
      : Array.from({ length: maximumColumn + 1 }, (_, column) => column);
    if (!allowedColumns.length) allowedColumns.push(preferredColumn);

    for (const column of allowedColumns) {
      const candidateRange = { column, columnSpan };
      let top = desiredTop;
      for (const existing of placed) {
        if (!readingRangesOverlap(candidateRange, existing)) continue;
        if (existing.bottom + rowGap > top) top = existing.bottom + rowGap;
      }
      if (top + height + edgePadding > canvasHeight) {
        let upwardTop = desiredTop;
        const blockers = placed
          .filter((existing) => readingRangesOverlap(candidateRange, existing))
          .sort((left, right) => right.top - left.top);
        for (const existing of blockers) {
          const overlapsVertically = upwardTop < existing.bottom + rowGap
            && existing.top - rowGap < upwardTop + height;
          if (overlapsVertically) upwardTop = existing.top - rowGap - height;
        }
        const fitsAbove = upwardTop >= edgePadding
          && blockers.every((existing) => (
            upwardTop + height + rowGap <= existing.top
            || upwardTop >= existing.bottom + rowGap
          ));
        if (fitsAbove) top = upwardTop;
      }
      const candidate = {
        column,
        columnSpan,
        top,
        overflow: Math.max(0, top + height + edgePadding - canvasHeight),
        displacement: Math.abs(top - desiredTop),
        preferenceDistance: Math.abs(column - preferredColumn),
      };
      if (
        !best
        || candidate.overflow < best.overflow
        || (
          candidate.overflow === best.overflow
          && candidate.displacement < best.displacement
        )
        || (
          candidate.overflow === best.overflow
          && candidate.displacement === best.displacement
          && candidate.preferenceDistance < best.preferenceDistance
        )
        || (
          candidate.overflow === best.overflow
          && candidate.displacement === best.displacement
          && candidate.preferenceDistance === best.preferenceDistance
          && candidate.column < best.column
        )
      ) {
        best = candidate;
      }
    }

    const result = {
      ...item,
      column: best.column,
      columnSpan: best.columnSpan,
      anchorPosition,
      desiredTop,
      displacement: Math.abs(best.top - desiredTop),
      top: best.top,
      bottom: best.top + height,
      left: best.column * (columnWidth + columnGap),
      width: columnWidth * best.columnSpan + columnGap * (best.columnSpan - 1),
      height,
    };
    placed.push(result);
  }

  return {
    cards: placed,
    requiredHeight: placed.reduce((maximum, item) => Math.max(maximum, item.bottom + edgePadding), 0),
    maximumDisplacement: placed.reduce((maximum, item) => Math.max(maximum, item.displacement), 0),
  };
}

export { MINUTES_PER_DAY };
