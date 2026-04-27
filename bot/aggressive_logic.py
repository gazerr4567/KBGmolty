import math

class AggressiveAgent:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.last_pos = {'x': 0, 'y': 0}
        self.stuck_count = 0
        self.is_healing_mode = False 

    def get_dist(self, p1, p2):
        return math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)

    def run_logic(self, game_state):
        # 1. AMBIL DATA DASAR
        player = game_state.get('player') or game_state.get('me')
        if not player or player.get('hp', 0) <= 0: return
            
        enemies = game_state.get('enemies', [])
        items = game_state.get('items', [])
        inventory = str(game_state.get('inventory', []))
        raw_inv = game_state.get('inventory', [])
        current_region = game_state.get('currentRegion', {})

        # --- STRATEGI 1: ANTI-DEATH ZONE (PRIORITAS MUTLAK) ---
        # Jika di zona merah, segera lari ke zona aman terdekat
        if current_region.get('isDeathZone'):
            self.bot.move_to_safe_zone() # Fungsi internal untuk lari dari zona
            return

        # 2. LOGIKA BUANG ITEM SAMPAH
        if len(raw_inv) >= 9:
            for item in raw_inv:
                if item.get('type') not in ['Katana', 'Sniper', 'Bandage', 'Medkit', 'Vest', 'Helmet']:
                    self.bot.drop_item(item.get('id'))
                    break 

        current_hp = player.get('hp', 100)

        # 3. LOGIKA PENYEMBUHAN (HP < 20)
        if current_hp <= 20: self.is_healing_mode = True
        elif current_hp >= 90: self.is_healing_mode = False

        if self.is_healing_mode:
            if enemies:
                avg_x = sum(e['x'] for e in enemies) / len(enemies)
                avg_y = sum(e['y'] for e in enemies) / len(enemies)
                self.bot.move_to(player['x'] + (player['x'] - avg_x), player['y'] + (player['y'] - avg_y))
            if 'Bandage' in inventory: self.bot.use_item('Bandage')
            return

        # 4. LOGIKA ANTI-GANK (2+ Musuh)
        if len(enemies) >= 2:
            avg_x = sum(e['x'] for e in enemies) / len(enemies)
            avg_y = sum(e['y'] for e in enemies) / len(enemies)
            self.bot.move_to(player['x'] + (player['x'] - avg_x), player['y'] + (player['y'] - avg_y))
            return

        # 5. LOGIKA SERANGAN PEMAIN (HP > 60)
        target = min(enemies, key=lambda e: e.get('hp', 100)) if enemies else None
        if target and current_hp > 60:
            dist = self.get_dist(player, target)
            self.bot.move_to(target['x'], target['y'])
            if dist < 1.5: self.bot.use_skill('all')
            self.bot.attack(target['id'])
            return

        # 6. STRATEGI EKONOMI ($SMOLTZ & LOOTING)
        elif not target:
            # A. Cari Senjata/Armor Dulu
            current_weapon = player.get('weapon', 'Fist')
            priority_items = [i for i in items if i.get('type') in ['Katana', 'Sniper', 'Vest', 'Helmet']]
            if priority_items:
                best_item = min(priority_items, key=lambda i: self.get_dist(player, i))
                self.bot.move_to(best_item['x'], best_item['y'])
                self.bot.pickup(best_item['id'])
                self.bot.equip(best_item['id'])
                return

            # B. Berburu $sMoltz (Monster/Guardian/Supply Caches)
            # Guardian/Monster sering membawa sMoltz yang jatuh saat mati
            objects = game_state.get('objects', []) # Caches atau Monsters
            if objects:
                best_obj = min(objects, key=lambda o: self.get_dist(player, o))
                self.bot.move_to(best_obj['x'], best_obj['y'])
                self.bot.interact(best_obj['id']) # Ambil/Interaksi untuk sMoltz
                return
            
            # C. Cari Loot Umum (Explore)
            self.bot.find_loot()

        # 7. ANTI-STUCK
        if player['x'] == self.last_pos['x'] and player['y'] == self.last_pos['y']:
            self.stuck_count += 1
        else: self.stuck_count = 0
        self.last_pos = {'x': player['x'], 'y': player['y']}
        if self.stuck_count > 2: 
            self.bot.move_to(player['x'] + 2, player['y'] - 1)
