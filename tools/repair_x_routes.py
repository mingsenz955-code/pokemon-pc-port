"""Restore exit records using matching objects in the recovered TMX files."""
import xml.etree.ElementTree as ET


def repair_routes(data, tables):
    maps = data/'assets/Map'
    town_path = maps/'map1501.tmx'
    town = ET.parse(town_path)
    exits = town.findall("./objectgroup[@name='spriteLayer']/object/properties/property[@name='toExit']/../..")
    exit_ids = sorted({obj.get('name') for obj in exits if not obj.get('gid')})
    if not {'150101', '150102', '150103', '150117'} <= set(exit_ids):
        raise ValueError('Recovered Morpheus town is missing its original connections')
    tables['VillageMap']['1501'].update(fileName=town_path.name, name='墨菲斯',
                                       exitIds=','.join(exit_ids))

    sea_path = maps/'map1101.tmx'
    sea = ET.parse(sea_path)
    scenery = sea.find("./objectgroup[@name='spriteTileLayer']")
    portal = scenery.find("object[@name='110108']")
    if portal is None or portal.get('gid') or portal.find(
            "./properties/property[@name='toExit'][@value='570102']") is None:
        raise ValueError('Recovered underwater portal does not match its return exit')
    scenery.remove(portal)
    sea.find("./objectgroup[@name='spriteLayer']").append(portal)
    sea.write(sea_path, encoding='utf-8', xml_declaration=True)

    city_path = maps/'map2101.tmx'
    city = ET.parse(city_path)
    marker = city.find("./objectgroup[@name='spriteTileLayer']/object[@name='210102']")
    if marker is None:
        raise ValueError('Recovered Light City landing marker is missing')
    layer = city.find("./objectgroup[@name='spriteLayer']")
    landing = ET.SubElement(layer, 'object', {
        key: marker.get(key) for key in ('name', 'x', 'y', 'width', 'height')
    })
    # The original map points at the northern door marker by name. Register
    # a landing in front of it without making the decorative tile an exit.
    ET.SubElement(ET.SubElement(landing, 'properties'), 'property', name='face', value='1')
    city.write(city_path, encoding='utf-8', xml_declaration=True)
    tables['VillageMap']['2101']['exitIds'] = '210101,210102'

    cave_path = maps/'map7502.tmx'
    cave = ET.parse(cave_path)
    rock = cave.find("./objectgroup[@name='spriteTileLayer']/object[@x='188.0'][@y='1464.0']")
    if rock is None or rock.get('gid') is None:
        raise ValueError('Recovered floor 2 switch decoration is missing')
    properties = rock.find('properties')
    if properties is None:
        properties = ET.SubElement(rock, 'properties')
    # This decorative stone occupies the only trigger tile of area 750201.
    ET.SubElement(properties, 'property', name='pcWalkThrough', value='1')
    cave.write(cave_path, encoding='utf-8', xml_declaration=True)
