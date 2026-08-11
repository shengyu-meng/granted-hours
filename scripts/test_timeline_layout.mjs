#!/usr/bin/env node
import assert from "node:assert/strict";
import {
  layoutTimelineEvents,
  layoutTimelineReadingCards,
  timeToMinutes,
} from "../src/timetable/timeline-layout.js";

assert.equal(timeToMinutes("00:00"), 0);
assert.equal(timeToMinutes("03:17"), 197);
assert.equal(timeToMinutes("24:00"), 1440);
assert.throws(() => timeToMinutes("24:01"), /Invalid timetable time/);

const events = [
  { id: "assigned", origin: "assigned", start: "04:17", end: "24:00" },
  { id: "scan-a", origin: "background", start: "08:40", end: "09:20" },
  { id: "scan-b", origin: "background", start: "09:00", end: "09:10" },
  { id: "scan-c", origin: "background", start: "14:00", end: "14:05" },
  { id: "self", origin: "self", start: "03:17", end: "04:17" },
];
const laidOut = layoutTimelineEvents(events);
const byId = new Map(laidOut.map((entry) => [entry.event.id, entry]));

assert.equal(byId.get("self").laneCount, 1);
assert.equal(byId.get("self").durationMinutes, 60);
assert.equal(byId.get("assigned").lane, 0);
assert.equal(byId.get("assigned").laneCount, 3);
assert.equal(byId.get("scan-a").lane, 1);
assert.equal(byId.get("scan-b").lane, 2);
assert.equal(byId.get("scan-c").lane, 1, "a later non-overlapping pulse should reuse the free lane");
assert.equal(byId.get("scan-c").durationMinutes, 5);
assert.equal(byId.get("assigned").overlapGroup, byId.get("scan-c").overlapGroup);
assert.notEqual(byId.get("self").overlapGroup, byId.get("assigned").overlapGroup);

const adjacent = layoutTimelineEvents([
  { id: "a", origin: "assigned", start: "10:00", end: "11:00" },
  { id: "b", origin: "background", start: "11:00", end: "12:00" },
]);
assert.deepEqual(adjacent.map((entry) => entry.laneCount), [1, 1]);
assert.notEqual(adjacent[0].overlapGroup, adjacent[1].overlapGroup);

assert.throws(
  () => layoutTimelineEvents([{ origin: "assigned", start: "12:00", end: "11:00" }]),
  /Invalid event window/,
);

const readingItems = [
  { key: "early-wide", startMinute: 30, anchorMinute: 86, anchorRatio: 0.5, height: 112, preferredColumn: 0, columnSpan: 2 },
  { key: "routine-a", startMinute: 35, height: 48, preferredColumn: 0, columnSpan: 1 },
  { key: "routine-b", startMinute: 35, height: 48, preferredColumn: 1, columnSpan: 1 },
  { key: "late", startMinute: 1439, height: 48, preferredColumn: 1, columnSpan: 1 },
];
const readingOptions = {
  columnCount: 2,
  columnGap: 6,
  rowGap: 4,
  canvasWidth: 400,
  canvasHeight: 1440,
  minuteHeight: 1,
  edgePadding: 4,
};
const firstReadingLayout = layoutTimelineReadingCards(readingItems, readingOptions);
const secondReadingLayout = layoutTimelineReadingCards(readingItems, readingOptions);
assert.deepEqual(firstReadingLayout, secondReadingLayout, "reading placement must be deterministic");
assert.equal(
  firstReadingLayout.cards.find((card) => card.key === "early-wide").top,
  30,
  "a reading card should be centered on its representative stratum when space permits",
);
for (const card of firstReadingLayout.cards) {
  assert.ok(card.top >= 4);
  assert.ok(card.bottom <= 1440);
}
for (let leftIndex = 0; leftIndex < firstReadingLayout.cards.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < firstReadingLayout.cards.length; rightIndex += 1) {
    const left = firstReadingLayout.cards[leftIndex];
    const right = firstReadingLayout.cards[rightIndex];
    const horizontalOverlap = left.left < right.left + right.width
      && right.left < left.left + left.width;
    const verticalOverlap = left.top < right.bottom && right.top < left.bottom;
    assert.ok(!(horizontalOverlap && verticalOverlap), JSON.stringify({ left, right }));
  }
}

console.log(JSON.stringify({ passed: true, cases: 5 }));
