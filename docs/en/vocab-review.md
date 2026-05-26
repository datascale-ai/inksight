# Vocabulary Review Mode

`VOCAB_REVIEW` is a built-in spaced repetition mode. Progress is stored per device MAC. The first version uses the bundled `core_en` deck and does not include spoken prompts or automatic answer checking.

## Firmware Environment

Dedicated vocabulary firmware environment:

```bash
platformio run -e epd_42_wroom32e_vocab_review
```

This target is for ESP32-WROOM32E with a 4.2-inch 400x300 black-and-white display. The function button uses `GPIO23`: connect one side to `GPIO23` and the other side to `GND`. This is a vocabulary-specific button firmware, separate from `epd_42_wroom32e_ai_chat`.

## Button Controls

- Outside vocabulary mode: long press enters vocabulary review.
- Front side: short press flips the card.
- Back side: short press cycles `Forgot / Fuzzy / Remember`.
- Back side: long press submits the selected rating and advances.

## Ratings

- `forgot`: due again in 10 minutes and records a lapse.
- `fuzzy`: due at least 1 day later, with a small ease decrease.
- `remember`: uses simplified SM-2 intervals: 1 day, 6 days, then grows by ease factor.

## Mode Settings

- `deck_id`: deck ID, default `core_en`.
- `daily_limit`: daily review cap, default `30`.
- `new_cards_per_day`: daily new-card cap, default `10`.

## Device API

```http
POST /api/device/{mac}/vocab/event
X-Device-Token: <device-token>
Content-Type: application/json
```

Example:

```json
{"action":"enter"}
```

Supported actions: `enter`, `flip`, `next_rating`, `submit_rating`. Rating submission may include `rating`: `forgot`, `fuzzy`, or `remember`.
