# Character Card Import

AiLoveU supports importing Character Tavern style PNG role cards as local AI companion profiles.

## Supported Format

The PNG file is expected to contain a `chara` metadata field in the PNG text chunks.

- `chara` is base64-encoded JSON
- the main persona payload is usually inside `data`

## Extracted Fields

The importer reads and normalizes fields such as:

- `name`
- `description`
- `personality`
- `scenario`
- `first_mes`
- `mes_example`
- `system_prompt`
- `post_history_instructions`
- `creator_notes`
- `tags`

## Import Flow

1. Open the PNG with Pillow
2. Read the `chara` text chunk
3. Decode base64 JSON
4. Build a local `CharacterProfile`
5. Generate a merged system prompt
6. Save the profile into the local character registry
7. Assign a dedicated memory namespace for this character

## Isolation Rules

After import, each character gets isolated state:

- independent system prompt
- independent opening message
- independent transcript history
- independent short-term session window
- independent long-term memory namespace

## Notes

- Character cards may be authored in English; the application separately handles reply-language adaptation at runtime.
- The original first message from the card is stored as-is unless you choose to localize it manually later.
