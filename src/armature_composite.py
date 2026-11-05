"""Preserve original normal/additive skin order when placing a skill effect."""
from PIL import Image, ImageChops


def additive_composite(destination, source, position):
    x, y = map(round, position)
    left, top = max(0, x), max(0, y)
    right, bottom = min(destination.width, x+source.width), min(destination.height, y+source.height)
    if left >= right or top >= bottom:
        return
    box = (left, top, right, bottom)
    src = source.crop((left-x, top-y, right-x, bottom-y)).convert('RGBa')
    dst = destination.crop(box).convert('RGBa')
    # Cocos premultiplied GL_ONE / GL_ONE, including alpha saturation.
    destination.paste(ImageChops.add(dst, src).convert('RGBA'), (left, top))


def composite(destination, art, position):
    layers = art.info.get('blend_layers')
    if layers is None:
        destination.alpha_composite(art, tuple(map(round, position)))
        return
    for layer, offset, additive in layers:
        point = (round(position[0]+offset[0]), round(position[1]+offset[1]))
        if additive:
            additive_composite(destination, layer, point)
        else:
            destination.alpha_composite(layer, point)


def transform_art(art, scale=1, rotate=False, mirror=False):
    """Resize/rotate both the flattened preview and its authored blend layers."""
    origin = art.info.get('origin', (art.width/2, art.height/2))
    result = art.resize((max(1, round(art.width*scale)), max(1, round(art.height*scale))), Image.Resampling.LANCZOS) if scale != 1 else art.copy()
    origin = (origin[0]*scale, origin[1]*scale)
    layers = []
    for layer, (x, y), additive in art.info.get('blend_layers', ()):
        image = layer.resize((max(1, round(layer.width*scale)), max(1, round(layer.height*scale))), Image.Resampling.LANCZOS) if scale != 1 else layer
        x, y = round(x*scale), round(y*scale)
        if rotate:
            x, y = result.width-x-image.width, result.height-y-image.height
            image = image.transpose(Image.Transpose.ROTATE_180)
        if mirror:
            x = result.width-x-image.width
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        layers.append((image, (x, y), additive))
    if rotate:
        result = result.transpose(Image.Transpose.ROTATE_180)
        origin = (result.width-origin[0], result.height-origin[1])
    if mirror:
        result = result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        origin = (result.width-origin[0], origin[1])
    result.info['origin'] = origin
    if 'blend_layers' in art.info:
        result.info['blend_layers'] = tuple(layers)
    return result
