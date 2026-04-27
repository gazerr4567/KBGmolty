import math

class AggressiveAgent:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.last_pos = {'x': 0, 'y': 0}
        self.stuck_count = 0

    def get_dist(self, p1, p2):
        return math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)

    def run_logic(self, game_state):
        player = game_state.get('player') or game_state.get('me')
        enemies = game_state.get('enemies', [])
        items = game_state.get('items', [])
        
        if not player or player.get('hp', 0) <= 0: return

        # --- STRATEGI 1: MANAJEMEN EP & HP ---
        # Gunakan 'Emergency Food' jika HP < 50 (Sesuai dokumentasi Sponsor System)
        if player.get('hp', 100) < 50:
            self.bot.use_item('Emergency Food')

        # --- STRATEGI 2: LOOTING SENJATA (Prioritas Utama) ---
        # Kelompok 2 (EP 0): Pickup & Equip tidak memakan waktu cooldown!
        current_weapon = player.get('weapon', 'Fist')
        if current_weapon in ['Fist', 'Knife', 'Sword']:
            high_tier_weapons = [i for i in items if i.get('type') in ['Katana', 'Sniper', 'Pistol']]
            if high_tier_weapons:
                target_wep = min(high_tier_weapons, key=lambda i: self.get_dist(player, i))
                self.bot.move_to(target_wep['x'], target_wep['y'])
                self.bot.pickup(target_wep['id']) # EP 0
                self.bot.equip(target_wep['id'])  # EP 0
                return

        # --- STRATEGI 3: ANTI-STUCK & DEATH ZONE ---
        # Sesuai aturan: Cek currentRegion.isDeathZone setiap turn!
        if game_state.get('currentRegion', {}).get('isDeathZone'):
            self.bot.move_to_safe_zone()
            return

        # --- STRATEGI 4: SERANGAN TAKTIS (Ranking by Kills) ---
        if player.get('ep', 0) >= 2: # Hanya serang jika EP cukup
            # Cari musuh dengan HP terendah untuk mengamankan Kill Ranking
            weak_enemy = None
            if enemies:
                weak_enemy = min(enemies, key=lambda e: e.get('hp', 100))
            
            if weak_enemy:
                dist = self.get_dist(player, weak_enemy)
                # Gunakan keunggulan Range (Pistol=1, Sniper=2)
                weapon_range = 0
                if 'Sniper' in current_weapon: weapon_range = 2
                elif 'Pistol' in current_weapon: weapon_range = 1

                if dist <= weapon_range:
                    self.bot.attack(weak_enemy['id'])
                else:
                    self.bot.move_to(weak_enemy['x'], weak_enemy['y'])
        else:
            # Jika EP rendah, lakukan 'rest' (Kelompok 1)
            self.bot.rest()

        # --- STRATEGI 5: CARI SMOLTZ (Ekonomi) ---
        if not enemies:
            # Interaksi dengan Supply Cache (EP 1)
            self.bot.find_loot()
