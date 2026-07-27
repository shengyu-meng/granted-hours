#!/usr/bin/env node
import assert from "node:assert/strict";
import { layoutTimelineEvents, timeToMinutes } from "../src/timetable/timeline-layout.js";

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

console.log(JSON.stringify({ passed: true, cases: 4 }));
