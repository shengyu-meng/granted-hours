import assert from "node:assert/strict";
import { layoutTimelineReadingCards } from "../src/timetable/timeline-layout.js";

const options = { columnCount: 4, columnGap: 4, rowGap: 4, canvasWidth: 1280, canvasHeight: 1200, minuteHeight: 1 };
const autonomous = { key: "autonomous", anchorMinute: 197, height: 268, columnSpan: 3 };
const digest = { key: "digest", anchorMinute: 490, height: 64, columnSpan: 2 };
const work = { key: "work", anchorMinute: 491, height: 64, columnSpan: 2 };
const result = layoutTimelineReadingCards([autonomous, digest, work], options);
assert.equal(result.cards.find((card) => card.key === "digest").afterKey, undefined);
assert.equal(result.cards.find((card) => card.key === "work").columnSpan, 2);
assert.notEqual(result.cards.find((card) => card.key === "digest").top, result.cards.find((card) => card.key === "autonomous").bottom + options.rowGap);
console.log("Flash schedule cards stay ordinary events.");
