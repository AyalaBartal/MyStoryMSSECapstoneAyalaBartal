/**
 * Card metadata for the picker UI.
 * Images are loaded from the public S3 bucket. Emoji kept as fallback.
 */

const CARDS_BUCKET_URL = "https://my-story-cards-691304835962.s3.amazonaws.com/cards";

export const CARDS = [
  {
    category: "hero",
    title: "Who's the hero?",
    options: [
      { value: "boy", label: "Boy", emoji: "👦", image: `${CARDS_BUCKET_URL}/hero/boy.png` },
      { value: "girl", label: "Girl", emoji: "👧", image: `${CARDS_BUCKET_URL}/hero/girl.png` },
    ],
  },
  {
    category: "theme",
    title: "Where does the story happen?",
    options: [
      { value: "space", label: "Space", emoji: "🚀", image: `${CARDS_BUCKET_URL}/theme/space.png` },
      { value: "under_the_sea", label: "Under the sea", emoji: "🌊", image: `${CARDS_BUCKET_URL}/theme/under_the_sea.png` },
      { value: "medieval_fantasy", label: "Medieval fantasy", emoji: "🏰", image: `${CARDS_BUCKET_URL}/theme/medieval_fantasy.png` },
      { value: "dinosaurs", label: "Dinosaurs", emoji: "🦖", image: `${CARDS_BUCKET_URL}/theme/dinosaurs.png` },
    ],
  },
  {
    category: "adventure",
    title: "What's the adventure?",
    options: [
      { value: "secret_map", label: "Secret map", emoji: "🗺️", image: `${CARDS_BUCKET_URL}/adventure/secret_map.png` },
      { value: "talking_animal", label: "Talking animal", emoji: "🦊", image: `${CARDS_BUCKET_URL}/adventure/talking_animal.png` },
      { value: "time_machine", label: "Time machine", emoji: "⏰", image: `${CARDS_BUCKET_URL}/adventure/time_machine.png` },
      { value: "magic_key", label: "Magic key", emoji: "🔑", image: `${CARDS_BUCKET_URL}/adventure/magic_key.png` },
    ],
  },
];