import math
import requests
import time

class MoltySuperAgent:
    def __init__(self):
        # KONFIGURASI API
        self.base_url = "https://moltyroyale.com"
        self.api_key = "21ae88b7-7323-4133-8f36-6bb831aa9590"
        self.headers = {"X-API-Key": self.api_key}
        
        # STATE INTERNAL
        self.game_id = None
        self.agent_id = None
        self.last_pos = {'regionId': None}
        self.stuck_count = 0
        
        # DATABASE JAWABAN GUARDIAN (Bisa ditambah sesuai temuan di game)
        self.riddle_db = {
            "capital of france": "Paris",
            "2 + 2": "4",
            "color of the sky": "Blue",
            "what is the answer to everything": "42"
        }

    def start_game(self):
        # 1. Cari Game yang sedang menunggu
        games = requests.get(f"{self.base_url}/games?status=waiting").json().get("data", [])
        if not games: return print("Tidak ada game tersedia.")
        
        self.game_id = games[0]["id"]
        
        # 2. Registrasi Agent
        res = requests.post(
            f"{self.base_url}/games/{self.game_id}/agents/register",
            headers=self.headers,
            json={"name": "UltimatumBot"}
        ).json()
        self.agent_id = res["data"]["id"]
        print(f"Bot Berhasil Join! ID: {self.agent_id}")

    def run_logic(self):
        while True:
            # AMBIL DATA STATE
            resp = requests.get(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/state", headers=self.headers)
            state = resp.json().get("data")
            
            if not state or not state["self"]["isAlive"]:
                print("Game Over atau Agent Mati.")
                break
            
            self_data = state["self"]
            curr_region = state["currentRegion"]
            inv = self_data.get('inventory', [])
            ep = self_data.get('ep', 0)
            hp = self_data.get('hp', 100)

            # === A. FREE ACTIONS (0 EP / Tanpa Turn) ===

            # 1. ANTI-CURSE & DIPLOMASI (Cek Whisper)
            for msg in state.get("recentMessages", []):
                if msg["senderId"] != self.agent_id and msg["type"] == "whisper":
                    text = msg["message"].lower()
                    # Cari jawaban di database teka-teki
                    found_answer = next((ans for ques, ans in self.riddle_db.items() if ques in text), None)
                    
                    if found_answer:
                        self.send_whisper(msg["senderId"], found_answer) # Jawab otomatis untuk angkat kutukan
                    else:
                        self.send_whisper(msg["senderId"], "Let's cooperate for survival.")

            # 2. AUTO PICKUP & SLOT SPONSOR (Limit 8/10)
            if len(inv) < 8:
                for item_entry in state.get("visibleItems", []):
                    if item_entry["regionId"] == self_data["regionId"]:
                        self.post_action({"type": "pickup", "itemId": item_entry["item"]["id"]})

            # 3. AUTO EQUIP SENJATA (Cari ATK Bonus tertinggi)
            weapons = [i for i in inv if i.get("category") == "weapon"]
            if weapons:
                best = max(weapons, key=lambda w: w.get('atkBonus', 0))
                current_atk = (self_data.get("equippedWeapon") or {}).get("atkBonus", 0)
                if best['atkBonus'] > current_atk:
                    self.post_action({"type": "equip", "itemId": best['id']})

            # === B. MAIN ACTIONS (Aksi Berbayar / 1 Turn) ===

            action = {"type": "explore"}
            thought = "Scanning area for threats and loot."

            # PRIORITAS 1: ANTI-DEATH ZONE
            if curr_region.get('isDeathZone'):
                safe_exit = curr_region.get("connections", [None])[0]
                action = {"type": "move", "regionId": safe_exit}
                thought = "URGENT: Escaping death zone!"

            # PRIORITAS 2: EMERGENCY HEAL (HP < 30)
            elif hp < 30:
                meds = next((i for i in inv if i.get("category") == "recovery"), None)
                if meds:
                    action = {"type": "use_item", "itemId": meds["id"]}
                    thought = "Low HP! Using recovery item."
                else:
                    # Cari fasilitas medis di region
                    fac = next((f for f in curr_region.get("interactables", []) if f["type"] == "heal" and not f["isUsed"]), None)
                    if fac:
                        action = {"type": "interact", "id": fac["id"]}
                        thought = "No meds, using medical facility."

            # PRIORITAS 3: LOW ENERGY (EP < 2)
            elif ep < 2:
                action = {"type": "rest"}
                thought = "Exhausted. Resting to recover Energy Points."

            # PRIORITAS 4: SERANG (Agent > Guardian > Monster)
            elif state.get("visibleAgents") or state.get("visibleMonsters"):
                # Pilih Agent dulu (PVP), lalu Guardian (Drop sMoltz besar), lalu Monster
                targets = [a for a in state.get("visibleAgents", []) if a["isAlive"]]
                if targets:
                    target = min(targets, key=lambda a: a['hp'])
                    action = {"type": "attack", "targetId": target["id"], "targetType": "agent"}
                    thought = f"Aggressive: Targeting weak agent {target['id']}."
                else:
                    monsters = state.get("visibleMonsters", [])
                    guardian = next((m for m in monsters if "Guardian" in m.get("type", "")), monsters[0] if monsters else None)
                    if guardian:
                        action = {"type": "attack", "targetId": guardian["id"], "targetType": "monster"}
                        thought = "Farming sMoltz from high-value target."

            # EKSEKUSI AKSI UTAMA
            self.post_action(action, thought)

            # ANTI-STUCK LOGIC
            if self_data['regionId'] == self.last_pos['regionId']:
                self.stuck_count += 1
                if self.stuck_count > 2:
                    self.post_action({"type": "explore"}, "Stuck detected, moving to new area.")
            else: self.stuck_count = 0
            self.last_pos = {'regionId': self_data['regionId']}

            time.sleep(60) # Menunggu 1 menit per giliran

    def post_action(self, action, thought="Acting strategically"):
        requests.post(
            f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/action",
            headers=self.headers,
            json={"action": action, "thought": {"reasoning": thought}}
        )

    def send_whisper(self, target_id, message):
        requests.post(
            f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/action",
            headers=self.headers,
            json={"action": {"type": "whisper", "targetId": target_id, "message": message}}
        )

# JALANKAN BOT
bot = MoltySuperAgent()
bot.start_game()
bot.run_logic()
