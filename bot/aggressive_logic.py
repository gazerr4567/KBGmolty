import math
import re

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
        raw_inv = game_state.get('inventory', [])
        inventory_str = str(raw_inv)
        current_region = game_state.get('currentRegion', {})
        AGENT_ID = player.get('id')
        current_weapon = player.get('weapon', 'Fist')
        current_hp = player.get('hp', 100)

        # === 2. RESPON RIDDLE GUARDIAN & PESAN (FREE ACTION) ===
        for msg in game_state.get("recentMessages", []):
            if msg.get("senderId") != AGENT_ID and msg.get("type") == "private":
                content = msg.get("message", "").lower()
                answer = None
                try:
                    nums = [int(n) for n in re.findall(r'\d+', content)]
                    if len(nums) >= 2:
                        if "+" in content: answer = str(nums[0] + nums[1])
                        elif "-" in content: answer = str(nums[0] - nums[1])
                        elif "*" in content: answer = str(nums[0] * nums[1])
                        elif "max" in content or "besar" in content: answer = str(max(nums))
                except: pass
                
                final_reply = answer if answer else "Focusing on survival."
                self.bot.whisper(msg["senderId"], final_reply)

        # === 3. MANAJEMEN TAS (Sponsor Slot & Anti-Sampah) ===
        if len(raw_inv) >= 8:
            for item in raw_inv:
                if item.get('type') not in ['Katana', 'Sniper', 'Medkit', 'Bandage', 'Vest', 'Helmet']:
                    self.bot.drop_item(item.get('id'))
                    break

        # --- 4. STRATEGI ANTI-DEATH ZONE (MUTLAK) ---
        if current_region.get('isDeathZone'):
            self.bot.move_to_safe_zone()
            return

        # --- 5. LOGIKA SURVIVAL OPORTUNIS (HP < 50 & TAS KOSONG) ---
        has_healing = any(h in inventory_str for h in ['Bandage', 'Medkit', 'Emergency Food'])
        
        if current_hp < 50 and not has_healing:
            # PRIORITAS SAMPINGAN: Ambil Senjata Bagus kalau "Sekalian Lewat" (Jarak < 2)
            god_tier = [i for i in items if i.get('type') in ['Katana', 'Sniper']]
            for gt in god_tier:
                if self.get_dist(player, gt) < 2:
                    self.bot.pickup(gt['id'])
                    self.bot.equip(gt['id'])
                    # Setelah ambil, tidak return, lanjut ke pencarian penyembuh di bawah

            # PRIORITAS UTAMA: Cari item penyembuh
            healing_on_ground = [i for i in items if i.get('type') in ['Medkit', 'Bandage', 'Emergency Food']]
            if healing_on_ground:
                best_heal = min(healing_on_ground, key=lambda i: self.get_dist(player, i))
                self.bot.move_to(best_heal['x'], best_heal['y'])
                self.bot.pickup(best_heal['id'])
                return
            else:
                self.bot.move_to_safe_zone()
                return

        # --- 6. LOGIKA PENYEMBUHAN KRITIS (HP < 20) ---
        if current_hp <= 20: self.is_healing_mode = True
        elif current_hp >= 90: self.is_healing_mode = False

        if self.is_healing_mode:
            if enemies:
                avg_x = sum(e['x'] for e in enemies) / len(enemies)
                avg_y = sum(e['y'] for e in enemies) / len(enemies)
                self.bot.move_to(player['x'] + (player['x'] - avg_x), player['y'] + (player['y'] - avg_y))
            if has_healing:
                if 'Bandage' in inventory_str: self.bot.use_item('Bandage')
                elif 'Medkit' in inventory_str: self.bot.use_item('Medkit')
            return

        # --- 7. LOGIKA SERANGAN & HUNTING ---
        target = min(enemies, key=lambda e: e.get('hp', 100)) if enemies else None
        target_sekarat = target and target.get('hp', 100) <= 40

        if target and (current_hp > 60 or target_sekarat):
            if len(enemies) >= 2 and not target_sekarat:
                self.bot.move_to_safe_zone()
            else:
                self.bot.move_to(target['x'], target['y'])
                if self.get_dist(player, target) < 1.5: self.bot.use_skill('all')
                self.bot.attack(target['id'])
            return

        # --- 8. STRATEGI EKONOMI (Guardian & Loot) ---
        elif not target:
            # A. Cari Senjata/Armor
            priority = [i for i in items if i.get('type') in ['Katana', 'Sniper', 'Vest', 'Helmet']]
            if priority:
                best = min(priority, key=lambda i: self.get_dist(player, i))
                self.bot.move_to(best['x'], best['y'])
                self.bot.pickup(best['id'])
                self.bot.equip(best['id'])
                return
            
            if current_weapon == 'Fist' and not priority:
                self.bot.move_to_safe_zone()
                return

            # B. Berburu Guardian
            monsters = game_state.get('visibleMonsters', [])
            guardians = [m for m in monsters if "Guardian" in m.get('type', '')]
            if guardians:
                g = guardians[0]
                self.bot.move_to(g['x'], g['y'])
                self.bot.attack(g['id'])
                return
            
            self.bot.find_loot()

        # 9. ANTI-STUCK
        if player['x'] == self.last_pos['x'] and player['y'] == self.last_pos['y']:
            self.stuck_count += 1
        else: self.stuck_count = 0
        self.last_pos = {'x': player['x'], 'y': player['y']}
        if self.stuck_count > 2: 
            self.bot.move_to(player['x'] + 2, player['y'] - 1)
