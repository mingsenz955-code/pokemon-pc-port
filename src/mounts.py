"""1.20.4 terrain traversal; see docs/MECHANICS_EVIDENCE.md for ARM references."""
from game_state import numbers


class Mounts:
    def __init__(self, state):
        self.state = state

    def owned(self):
        return [self.state.tables['Ride'][str(key)] for key in self.state.rides
                if str(key) in self.state.tables['Ride']]

    def active(self):
        key = self.state.trial_ride or self.state.ride
        if not self.state.trial_ride and int(key) not in [int(k) for k in self.state.rides]:
            return None
        return self.state.tables['Ride'].get(str(key))

    @staticmethod
    def terrains(row):
        # Ride.collidesAble uses 0 as ordinary ground, not the empty-list
        # sentinel used by unrelated inventory/event fields in numbers().
        return [int(value) for value in str(row['collidesAble']).split(',') if value.strip()]

    @staticmethod
    def accepts(row, terrain, map_type):
        return (row is not None and terrain in Mounts.terrains(row)
                and map_type not in numbers(row['mapTypeDisable']))

    def automatic(self, terrain, map_type):
        # compareRidesCollidesAble/onRideWithCollideTile only search kinds 2/3.
        # Flying and ground mounts must be selected by the player.
        return next((row for row in self.owned() if int(row['kind']) in (2, 3)
                     and self.accepts(row, terrain, map_type)), None)

    def can_enter(self, terrain, map_type):
        if terrain is None:
            return False  # Bounds remain solid, including for flying mounts.
        return (terrain == 0 or self.accepts(self.active(), terrain, map_type)
                or self.automatic(terrain, map_type) is not None)

    def can_fly(self, map_type):
        row = self.active()
        return row is not None and int(row['kind']) == 1 and map_type not in numbers(row['mapTypeDisable'])

    def enter(self, terrain, map_type):
        """Apply rideProcess only after the position has actually been accepted."""
        if not self.can_enter(terrain, map_type):
            return False
        if self.state.trial_ride:  # Original compareRideAble bypass during trial.
            return True
        if not self.accepts(self.active(), terrain, map_type):
            if terrain == 0:
                self.state.ride = 0
            else:
                row = self.automatic(terrain, map_type)
                if row:
                    self.state.ride = int(row['keyId'])
        return True

    def select(self, key, terrain, map_type):
        if self.state.trial_ride:
            raise ValueError('请先完成当前试乘剧情。')
        key = int(key)
        if key == 0:
            if terrain != 0:
                raise ValueError('此处不能收回坐骑')
        else:
            row = self.state.tables['Ride'].get(str(key))
            if key not in [int(k) for k in self.state.rides]:
                raise ValueError('尚未获得这只坐骑。')
            if terrain not in self.terrains(row):
                raise ValueError('该坐骑不适应此地形')
            if map_type in numbers(row['mapTypeDisable']):
                raise ValueError('该坐骑不适应此地图')
        previous = self.state.ride
        self.state.ride = key
        if key and key != previous:
            self.state.activities['ride_total'] = int(
                self.state.activities.get('ride_total', 0))+1

    def obstacle_ability(self, kind):
        row = self.active()
        return row is not None and int(kind) in numbers(row['obstacleAble']) and int(kind) != 0
