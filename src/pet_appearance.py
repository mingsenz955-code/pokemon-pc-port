"""Original quality name colors and the APK's getFlashAction tint sequence."""
from functools import lru_cache

# DataManager static initializer 0x2aa0b4, getFontColor 0x31a3f0.
QUALITY_COLORS = {1: (255, 255, 255), 2: (1, 127, 13), 3: (0, 123, 180),
                  4: (146, 0, 177), 5: (255, 229, 8), 6: (201, 2, 1)}
WHITE = (255, 255, 255)
# getFlashAction @ 0x2b93ac: 15 TintTo actions, each 0.4 seconds,
# RepeatForever. These are node tints, independent of PetQuality.
FLASH_TARGETS = ((255, 209, 45), WHITE, (238, 113, 35), WHITE,
                 (213, 44, 36), WHITE, (232, 128, 222), WHITE,
                 (123, 69, 223), WHITE, (15, 132, 229), WHITE,
                 (60, 161, 221), WHITE, (60, 176, 73))


def quality_color(pet):
    return QUALITY_COLORS.get(int(getattr(pet, 'quality', 1)), WHITE)


def flash_color(seconds):
    seconds = max(0.0, float(seconds))
    stage = seconds/.4
    whole = int(stage+1e-9)
    index = whole % len(FLASH_TARGETS)
    fraction = max(0.0, min(1.0, stage-whole))
    start = WHITE if whole == 0 else FLASH_TARGETS[(index-1) % len(FLASH_TARGETS)]
    target = FLASH_TARGETS[index]
    return tuple(round(a+(b-a)*fraction) for a, b in zip(start, target))


@lru_cache(maxsize=128)
def tint_lut(rgb):
    return tuple(round(value*color/255) for color in (*rgb, 255) for value in range(256))


def pet_flash(data, species, image, seconds, shiny=False):
    if not shiny and str(data.tables['Pet'][str(species)].get('flash', '0')) != '1':
        return image
    rgb = flash_color(seconds)
    if rgb == WHITE:
        return image
    result = image.point(tint_lut(rgb))
    result.info.update(image.info)
    return result
