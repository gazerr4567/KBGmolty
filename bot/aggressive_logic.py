import math
import requests
import time

class MoltySuperAgent:
    def __init__(self):
        # FIX URL API: Harus pakai sub-domain CDN/API
        self.base_url = "https://moltyroyale.com"
        self.api_key = "21ae88b7-7323-4133-8f36-6bb831aa9590"
        self.headers = {"X-API-Key": self.api_key}
        
        self.game_id = None
        self.agent_id = None
        self.last_pos = {'regionId': None}
        self.stuck_count = 0
        
        # DATABASE JAWABAN GUARDIAN
        self.riddle_db = {
            "capital of france": "Paris",
            "2 + 2": "4",
            "color of the sky": "Blue",
            "what is the answer to everything": "42"
        }

    def start_game(self):
        try:
            # 1. Cari Game
            print("Mencari room...")
            resp = requests.get(f"{self.base_url}/games?status=waiting", timeout=10)
            if resp.status_code != 200:
                print(f"Server Error: {resp.status_code}")
                return
            
            games = resp.json().get("data", [])
            if not games:
                print("Tidak ada game tersedia saat ini.")
                return
            
            self.game_id = games[0]["id"]
            
            # 2. Registrasi
            print(f"Mencoba join game: {self.game_id}")
            res = requests.post(
                f"{self.base_url}/games/{self.game_id}/agents/register",
                headers=self.headers,
                json={"name": "UltimatumBot"},
                timeout=10
            )
            
            data = res.json().get("data")
            if data:
                self.agent_id = data["id"]
                print(f"BERHASIL JOIN! ID: {self.agent_id}")
            else:
                print(f"Gagal Registrasi: {res.text}")
        except Exception as e:
            print(f"Error saat start_game: {e}")

    def run_logic(self):
        if not self.game_id or not self.agent_id:
            print("Bot belum terdaftar. Mematikan sistem...")
            return

        while True:
            try:
                # AMBIL DATA STATE
                resp = requests.get(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/state", headers=self.headers, timeout=10)
                state = resp.json().get("data")
                
                if not state or not state["self"]["isAlive"]:
                    print("Agent Mati atau Game Selesai.")
                    break
                
                self_data = state["self"]
                curr_region = state["currentRegion"]
                inv = self_data.get('inventory', [])
                ep = self_data.get('ep', 0)
                hp = self_data.get('hp', 100)

                # --- FREE ACTIONS ---
                # 1. Balas Whisper (Anti-Curse)
                for msg in state.get("recentMessages", []):
                    if msg["senderId"] != self.agent_id and msg.get("type") == "whisper":
                        text = msg["message"].lower()
                        ans = next((a for q, a in self.riddle_db.items() if q in text), "Focusing.")
                        self.send_whisper(msg["senderId"], ans)

                # 2. Auto Pickup (Slot 8/10)
                if len(inv) < 8:
                    for item_entry in state.get("visibleItems", []):
                        if item_entry["regionId"] == self_data["regionId"]:
                            self.post_action({"type": "pickup", "itemId": item_entry["item"]["id"]})

                # 3. Auto Equip
                weapons = [i for i in inv if i.get("category") == "weapon"]
                if weapons:
                    best = max(weapons, key=lambda w: w.get('atkBonus', 0))
                    curr_atk = (self_data.get("equippedWeapon") or {}).get("atkBonus", 0)
                    if best['atkBonus'] > curr_atk:
                        self.post_action({"type": "equip", "itemId": best['id']})

                # --- MAIN ACTIONS ---
                action = {"type": "explore"}
                reason = "Searching..."

                # Priority Logic
                if curr_region.get('isDeathZone'):
                    safe_exits = curr_region.get("connections", [])
                    action = {"type": "move", "regionId": safe_exits[0] if safe_exits else None}
                    reason = "RUNNING FROM GAS!"
                elif hp < 30:
                    meds = next((i for i in inv if i.get("category") == "recovery"), None)
                    if meds: action = {"type": "use_item", "itemId": meds["id"]}
                    else:
                        fac = next((f for f in curr_region.get("interactables", []) if f["type"] == "heal" and not f["isUsed"]), None)
                        if fac: action = {"type": "interact", "id": fac["id"]}
                    reason = "Healing..."
                elif ep < 2:
                    action = {"type": "rest"}
                    reason = "Recovering EP"
                else:
                    # Attack Logic
                    targets = [a for a in state.get("visibleAgents", []) if a["isAlive"] and a["regionId"] == self_data["regionId"]]
                    if targets:
                        target = min(targets, key=lambda a: a['hp'])
                        action = {"type": "attack", "targetId": target["id"], "targetType": "agent"}
                        reason = "PVP Combat"
                    else:
                        monsters = [m for m in state.get("visibleMonsters", []) if m["regionId"] == self_data["regionId"]]
                        if monsters:
                            guardian = next((m for m in monsters if "Guardian" in m.get("type", "")), monsters[0])
                            action = {"type": "attack", "targetId": guardian["id"], "targetType": "monster"}
                            reason = "Farming sMoltz"

                self.post_action(action, reason)

                # Anti-Stuck
                if self_data['regionId'] == self.last_pos['regionId']:
                    self.stuck_count += 1
                    if self.stuck_count > 2:
                        self.post_action({"type": "explore"}, "Relocating...")
                else: self.stuck_count = 0
                self.last_pos = {'regionId': self_data['regionId']}

            except Exception as e:
                print(f"Siklus error (mencoba lagi dalam 10 detik): {e}")
                time.sleep(10)
                continue

            time.sleep(60)

    def post_action(self, action, thought):
        try:
            requests.post(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/action", 
                          headers=self.headers, json={"action": action, "thought": {"reasoning": thought}}, timeout=10)
        except: pass

    def send_whisper(self, target_id, message):
        try:
            requests.post(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/action",
                          headers=self.headers, json={"action": {"type": "whisper", "targetId": target_id, "message": message}}, timeout=10)
        except: pass

# JALANKAN
bot = MoltySuperAgent()
bot.start_game()
bot.run_logic()
