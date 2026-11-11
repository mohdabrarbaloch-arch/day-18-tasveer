# Usage

## The studio

The left column is the composer, the right is the stage.

### Writing a prompt

Be specific about three things: **subject**, **mood**, **style**.

```
a lone lighthouse on a stormy coast at night, cinematic
```

- *subject* — "lighthouse", "coast"
- *mood* — "stormy", "night" (these shift the palette cold and dark)
- *style* — "cinematic" (picks the amber-and-navy preset)

The renderer reads mood words, not meaning. Words that actually do something:

| Category | Words |
|---|---|
| Warm | warm, sunset, golden, fire, desert |
| Cold | cold, ice, winter, storm, ocean, forest |
| Light | bright, pastel, vivid, neon |
| Dark | dark, night, muted, noir |
| Composition | portrait, face, person, character, product, object → centred |
| Composition | landscape, mountain, sea, city, skyline → horizon |
| Composition | abstract, pattern, texture → scattered |

Longer prompts produce denser compositions. A negative prompt containing
"minimal" or "clean" thins them out again.

### Styles

| Key | Feel |
|---|---|
| `cinematic` | amber and navy, high contrast, film grain |
| `anime` | bright pastels, soft, low grain |
| `oil` | warm browns, heavy texture, painterly |
| `cyberpunk` | magenta and cyan on near-black, sharp accents |
| `minimal` | near-white, very low contrast, sparse |
| `watercolor` | pale washes, very soft, light grain |
| `render3d` | cool greys, radial light, product-shot feel |
| `noir` | monochrome, heavy vignette, strong grain |

If you don't pick one, the prompt decides — "neon cyberpunk street" selects
`cyberpunk` automatically.

### Aspect ratios

| Ratio | Pixels | Use for |
|---|---|---|
| 1:1 | 1024 × 1024 | feed posts, avatars |
| 3:2 | 1216 × 812 | landscape photos |
| 2:3 | 812 × 1216 | portrait photos |
| 16:9 | 1280 × 720 | headers, slides |
| 9:16 | 720 × 1280 | phone wallpapers, stories |
| 4:5 | 900 × 1125 | Instagram portrait |

### Seeds

Every generation gets a seed. Every tile within it gets a derived seed
(`base + i × 7919`). Same prompt + same seed = byte-identical PNG.

This is how you iterate:

1. Generate. Find a composition you like.
2. Click **Reuse seed** — it restores both the prompt and the seed.
3. Change one word. Generate again. The composition holds, the mood shifts.

### Credits

60 on signup, 1 per generation (a generation is 4 images). The pill in the
header shows your balance. At zero you get a 402 and a nudge to top up.

## The gallery

Everything with `is_public = true`, newest first. Filter by style with the chips.
Click any tile for the lightbox and a download button.

To share your own work, tick **Share to gallery** in the Advanced panel before
generating. It is off by default — nothing you make is public unless you say so.

## Your history

The strip at the bottom of the studio shows your last 12 generations. Click one
to load it back into the stage. Delete from the API:

```bash
curl -X DELETE http://127.0.0.1:8000/api/generations/42 \
  -H "Authorization: Bearer $TOKEN"
```

That removes the database rows and the PNGs from disk.

## Keyboard

| Key | Action |
|---|---|
| `Esc` | close the lightbox, then the auth modal |
| `Tab` | move between chips and fields |
| `Enter` | submit the prompt form (from the textarea: `Ctrl/Cmd + Enter`) |

## Common workflows

**Making a set of matching images**

Pick a seed, keep it, change only the subject word. The palette and composition
stay consistent because they come from the mood words and the seed, not the
subject.

**Making a phone wallpaper**

9:16, and keep the prompt short. Dense prompts at 9:16 get busy in a way that
reads badly on a lock screen.

**Making something for a slide header**

16:9, `minimal` or `cinematic`, and put "abstract" in the prompt so the
composition scatters rather than centring on a subject that will fight your text.

**Reproducing someone else's image**

You need three things: the prompt, the style, and the seed. All three are shown
in the result header and in the API response. With all three you get the exact
same bytes.
