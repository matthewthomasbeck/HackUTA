# Paper-cut redesign: deferred

These items are left over from the iOS paper-cut redesign (`feat/ios-paper-cut-redesign`, plan
`docs/superpowers/plans/2026-11-14-ios-paper-cut-redesign.md`). They're kept here rather than in `eric-ios.md`.

- **App icon reads "^-1".** The current icon art spells the superscript wrong. A corrected icon is coming. Replace
  `ios/Calypso/Assets.xcassets/AppIcon.appiconset/AppIcon.png` when it arrives.
- **No hero caption or person photo data.** `DayEvent` and `Person` have no caption or "family photo" field, so the
  Today hero shows without a caption and person detail leaves the photo out. This needs a contract change
  (`models.py` + `Models.swift`) first.
- **Dark mode isn't designed.** The app forces `.preferredColorScheme(.light)` at the root.
- **Not driven by hand in the simulator.** VoiceOver, taps and swipe gestures (including edge swipe-back on person
  detail, and "tap a person, then swipe at once") were checked through unit tests, accessibility labels and
  screenshots, not by driving them by hand. Do a hands-on pass on a device before the demo.
- **Drift we can't match (and why):**
  - *Moment card title*: Figma has a short title plus a Callout summary. `DayEvent` has only `summary`, so the card
    shows the summary as its Headline (plan ruling).
  - *Edit-name sheet Save is disabled while blank*: Figma shows Save as an enabled Primary even with an empty field.
    The app disables Save until a name is typed, using the shared dashed disabled style, never an opacity fade.
  - *Tab bar on debug routes*: the `-screen today/people/person-*` routes render without the tab bar; `home` and
    `account` show it. This only affects screenshots.
  - *Permission and checkmark glyphs*: Figma has no `Icon / *` for the "Allowed" checkmark, so it stays an SF Symbol.
    The people-row chevron is `Icon / Chevron Left` mirrored, since Figma has no right chevron.
  - *DaySwitcher at xxxLarge and above*: the two buttons stack, because "‹ Yesterday" + "Tomorrow" don't fit side by
    side at that size.
- **Debug specimen**: the `design-system` route's swatch labels use 12pt system text. It's a developer-only screen,
  compiled only into DEBUG builds and reached only through the `-screen` argument.
