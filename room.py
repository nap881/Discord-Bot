import random
import string
from wca_calc import parse_time, format_time


def generate_code():
    return ''.join(random.choices(string.digits, k=6))


class Room:
    def __init__(self, host_id, channel_id, cube_type, rounds, scramble_fn):
        self.host_id = host_id
        self.channel_id = channel_id
        self.cube_type = cube_type
        self.rounds = rounds
        self.scramble_fn = scramble_fn
        self.players = {}
        self.scrambles = []
        self.current_round = 0
        self.state = "waiting"
        self.times = {}

    def add_player(self, user_id, display_name):
        if user_id not in self.players:
            self.players[user_id] = display_name

    def start(self):
        self.state = "active"
        self.scrambles = [self.scramble_fn() for _ in range(self.rounds)]
        self.times = {uid: [None] * self.rounds for uid in self.players}
        self.current_round = 0

    def submit_time(self, user_id, time_str):
        if user_id not in self.players:
            return False, "You are not in this room."
        if self.state != "active":
            return False, "Room is not active."
        if self.times[user_id][self.current_round] is not None:
            return False, "You already submitted a time for this round."
        try:
            parsed = parse_time(time_str)
        except Exception:
            return False, f"Could not parse '{time_str}' as a valid time."
        self.times[user_id][self.current_round] = parsed
        return True, format_time(parsed)

    def all_submitted(self):
        return all(
            self.times[uid][self.current_round] is not None
            for uid in self.players
        )

    def advance_round(self):
        for uid in self.players:
            if self.times[uid][self.current_round] is None:
                self.times[uid][self.current_round] = float('inf')
        self.current_round += 1
        if self.current_round >= self.rounds:
            self.state = "finished"
            return True
        return False

    def round_results(self, rnd):
        lines = []
        for uid, name in self.players.items():
            t = self.times[uid][rnd]
            lines.append(f"**{name}** — {format_time(t)}")
        return lines

    def calculate_average(self, user_id):
        all_times = self.times[user_id]
        n = len(all_times)
        if n < 5:
            if any(t == float('inf') for t in all_times):
                return float('inf')
            return round(sum(all_times) / n, 2)
        sorted_times = sorted(all_times)
        trimmed = sorted_times[1:-1]
        if any(t == float('inf') for t in trimmed):
            return float('inf')
        return round(sum(trimmed) / len(trimmed), 2)

    def leaderboard(self):
        results = []
        for uid, name in self.players.items():
            avg = self.calculate_average(uid)
            results.append((uid, name, avg))
        results.sort(key=lambda x: x[2])
        return results


rooms = {}


def create_room(host_id, channel_id, cube_type, rounds, scramble_fn):
    code = generate_code()
    while code in rooms:
        code = generate_code()
    room = Room(host_id, channel_id, cube_type, rounds, scramble_fn)
    rooms[code] = room
    return code


def find_player_room(channel_id, user_id):
    for code, room in rooms.items():
        if room.channel_id == channel_id and user_id in room.players and room.state == "active":
            return code, room
    return None, None

