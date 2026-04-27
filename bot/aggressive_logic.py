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
        inventory = str(game_state.get('inventory', []))
        raw_inv = game_state.get('inventory', [])
        current_region = game_state.get('currentRegion', {})
        AGENT_ID = player.get('id')

        # === 2. RESPOND TO WHISPERS & RIDDLES (FREE ACTION) ===
        for msg in game_state.get("recentMessages", []):
            if msg.get("senderId") != AGENT_ID and msg.get("type") == "private":
                content = msg.get("message", "").lower()
                answer = None
                
                try:
                    nums = [int(n) for n in re.findall(r'\d+', content)]
                    # Logika Matematika & Perbandingan
                    if len(nums) >= 2:
                        if "+" in content: answer = str(nums[0] + nums[1])
                        elif "-" in content: answer = str(nums[0] - nums[1])
                        elif "*" in content: answer = str(nums[0] * nums[1])
                        elif any(x in content for x in ["besar", "max", "greater"]): answer = str(max(nums))
                        elif any(x in content for x in ["kecil", "min", "smaller"]): answer = str(min(nums))
                except: pass

                # Logika Kata Kunci
                if not answer:
                    keywords = {"color": "red", "direction": "north", "status": "active", "who": "agent", "moltz": "1000"}
                    for key, val in keywords.items():
                        if key in content:
                            answer = val
                            break

                final_reply = answer if answer else "Let's cooperate to reach the late phase."
                # Menggunakan method whisper dari bot_instance
                self.bot.whisper(msg["senderId"], final_reply)

        # --- 3. STRATEGI ANTI-DEATH ZONE (PRIORITAS MUTLAK) ---
        if current_region.get('isDeathZone'):
            self.bot.move_to_safe_zone()
            return

        # 4. LOGIKA BUANG ITEM SAMPAH
        if len(raw_inv) >= 9:
            for item in raw_inv:
                if item.get('type') not in ['Katana', 'Sniper', 'Bandage', 'Medkit', 'Vest', 'Helmet']:
                    self.bot.drop_item(item.get('id'))
                    break 

        current_hp = player.get('hp', 100)

        # 5. LOGIKA PENYEMBUHAN (HP < 20)
        if current_hp <= 20: self.is_healing_mode = True
        elif current_hp >= 90: self.is_healing_mode = False

        if self.is_healing_mode:
            if enemies:
                avg_x = sum(e['x'] for e in enemies) / len(enemies)
                avg_y = sum(e['y'] for e in enemies) / len(enemies)
                self.bot.move_to(player['x'] + (player['x'] - avg_x), player['y'] + (player['y'] - avg_y))
            if 'Bandage' in inventory: self.bot.use_item('Bandage')
            return

        # 6. LOGIKA ANTI-GANK (2+ Musuh)
        if len(enemies) >= 2:
            avg_x = sum(e['x'] for e in enemies) / len(enemies)
            avg_y = sum(e['y'] for e in enemies) / len(enemies)
            self.bot.move_to(player['x'] + (player['x'] - avg_x), player['y'] + (player['y'] - avg_y))
            return

        # 7. LOGIKA SERANGAN PEMAIN (HP > 60)
        target = min(enemies, key=lambda e: e.get('hp', 100)) if enemies else None
        if target and current_hp > 60:
            dist = self.get_dist(player, target)
            self.bot.move_to(target['x'], target['y'])
            if dist < 1.5: self.bot.use_skill('all')
            self.bot.attack(target['id'])
            return

        # 8. STRATEGI EKONOMI ($SMOLTZ & LOOTING)
        elif not target:
            priority_items = [i for i in items if i.get('type') in ['Katana', 'Sniper', 'Vest', 'Helmet']]
            if priority_items:
                best_item = min(priority_items, key=lambda i: self.get_dist(player, i))
                self.bot.move_to(best_item['x'], best_item['y'])
                self.bot.pickup(best_item['id'])
                self.bot.equip(best_item['id'])
                return

            objects = game_state.get('objects', [])
            if objects:
                best_obj = min(objects, key=lambda o: self.get_dist(player, o))
                self.bot.move_to(best_obj['x'], best_obj['y'])
                self.bot.interact(best_obj['id'])
                return
            
            self.bot.find_loot()

        # 9. ANTI-STUCK
        if player['x'] == self.last_pos['x'] and player['y'] == self.last_pos['y']:
            self.stuck_count += 1
        else: self.stuck_count = 0
        self.last_pos = {'x': player['x'], 'y': player['y']}
        if self.stuck_count > 2: 
            self.bot.move_to(player['x'] + 2, player['y'] - 1)
