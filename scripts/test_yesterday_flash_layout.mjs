import assert from "node:assert/strict";
import { layoutTimelineReadingCards } from "../src/timetable/timeline-layout.js";

for (const width of [280, 360, 1280, 3600]) {
  const options = { columnCount: 4, columnGap: 4, rowGap: 4, canvasWidth: width, canvasHeight: 1200, minuteHeight: 1 };
  const autonomous = { key: "autonomous", anchorMinute: 197, anchorPosition: 197, anchorRatio: 0, height: 268, columnSpan: 3, allowedColumns: [0, 1] };
  const flash = { key: "flash", afterKey: "autonomous", anchorMinute: 490, anchorPosition: 490, anchorRatio: 0, height: 90, columnSpan: 3 };
  const intervening = { key: "routine", anchorMinute: 300, anchorPosition: 300, height: 80, columnSpan: 2 };
  const solo = layoutTimelineReadingCards([autonomous], options).cards[0];
  const result = layoutTimelineReadingCards([autonomous, intervening, flash], options);
  const primary = result.cards.find((card) => card.key === "autonomous");
  const secondary = result.cards.find((card) => card.key === "flash");
  assert.equal(primary.height, solo.height);
  assert.equal(primary.width, solo.width);
  assert.equal(primary.top, solo.top);
  assert.equal(secondary.top, primary.bottom + options.rowGap);
  assert.equal(secondary.left, primary.left);
  assert.equal(secondary.width, primary.width);
  assert.equal(secondary.anchorMinute, 490);
  for (const card of result.cards.filter((card) => card.key !== "flash")) {
    const overlaps = card.left < secondary.left + secondary.width && secondary.left < card.left + card.width
      && card.top < secondary.bottom && secondary.top < card.bottom;
    assert.equal(overlaps, false);
  }
}
assert.throws(() => layoutTimelineReadingCards([{ key: "flash", afterKey: "missing" }], {}), /requires a primary/);
console.log("Yesterday's Flash protected adjacency passed.");
