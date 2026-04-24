/**
 * Card metadata for the picker UI.
 *
 * `value` must match what the backend `cards_schema.json` accepts.
 * Adding a card here requires a matching entry in the backend schema.
 * Emojis are placeholders; swap for S3 illustrations post-capstone.
 */
export const CARDS = [
  {
    category: "hero",
    title: "Who's the hero?",
    options: [
      { value: "boy", label: "Boy", emoji: "👦" },
      { value: "girl", label: "Girl", emoji: "👧" },
    ],
  },
  {
    category: "theme",
    title: "Where does the story happen?",
    options: [
      { value: "space", label: "Space", emoji: "🚀" },
      { value: "under_the_sea", label: "Under the sea", emoji: "🌊" },
      { value: "medieval_fantasy", label: "Medieval fantasy", emoji: "🏰" },
      { value: "dinosaurs", label: "Dinosaurs", emoji: "🦖" },
    ],
  },
  {
    category: "challenge",
    title: "What's the challenge?",
    options: [
      { value: "asteroid", label: "Asteroid", emoji: "☄️" },
      { value: "wizard_witch", label: "Wizard or witch", emoji: "🧙" },
      { value: "dragon", label: "Dragon", emoji: "🐉" },
      { value: "volcano", label: "Volcano", emoji: "🌋" },
    ],
  },
  {
    category: "strength",
    title: "Their special strength?",
    options: [
      { value: "super_strong", label: "Super strong", emoji: "💪" },
      { value: "friendship", label: "Friendship", emoji: "🤝" },
      { value: "super_smart", label: "Super smart", emoji: "🧠" },
      { value: "super_speed", label: "Super speed", emoji: "⚡" },
    ],
  },
];