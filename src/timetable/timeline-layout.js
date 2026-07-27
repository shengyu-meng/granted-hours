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

export { MINUTES_PER_DAY };
