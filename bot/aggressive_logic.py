import math

class AggressiveAgent:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.burst_threshold = 0.5
        self.last_pos = {'x': 0, 'y': 0}
        self.stuck_count = 0

    def get_dist(self, p1, p2):
        return math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)

    def get_best_target(self, enemies, player_pos):
        if not enemies: return None
        best_enemy = None
        highest_score = -1
        for enemy in enemies:
            dist = self.get_dist(player_pos, enemy)
            # Skor: Prioritas HP rendah dan jarak dekat
            score = ((1 - enemy.get('hp', 1)) * 100) + ((1 / (dist + 1)) * 50)
            if score > highest_score:
                highest_score = score
                best_enemy = enemy
        return best_enemy

    def run_logic(self, game_state):
        player = game_state.get('player') or game_state.get('me')
        enemies = game_state.get('enemies', [])
        if not player or player.get('hp', 0) <= 0: return

        # --- LOGIKA ANTI-NYANGKUT ---
        if player['x'] == self.last_pos['x'] and player['y'] == self.last_pos['y']:
            self.stuck_count += 1
        else:
            self.stuck_count = 0
        self.last_pos = {'x': player['x'], 'y': player['y']}

        # Jika nyangkut lebih dari 3 frame, gerak acak untuk lepas
        if self.stuck_count > 3:
            self.bot.move_to(player['x'] + 2, player['y'] - 2)
            return

        # --- LOGIKA BERTAHAN (HEAL/KITING) ---
        if player.get('hp', 1) < 0.3 and enemies:
            closest = min(enemies, key=lambda e: self.get_dist(player, e))
            # Lari menjauh dari musuh terdekat
            self.bot.move_to(player['x'] * 2 - closest['x'], player['y'] * 2 - closest['y'])
            self.bot.attack(closest['id'])
            return

        target = self.get_best_target(enemies, player)
        
        if target:
            dist = self.get_dist(player, target)
            # Jaga jarak ideal (Kiting)
            if dist < 1.5:
                self.bot.move_to(player['x'] - 1, target['y']) # Mundur samping
            else:
                self.bot.move_to(target['x'], target['y']) # Kejar
            
            # Gunakan semua skill jika dekat atau musuh lemah
            if dist < 2 or target.get('hp', 1) < self.burst_threshold:
                self.bot.use_skill('all')
                
            self.bot.attack(target['id'])
        else:
            # Jika aman, cari item untuk memperkuat diri
            self.bot.find_loot()
