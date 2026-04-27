import math
import requests
import time

class AggressiveAgent: # Nama kelas disamakan agar main.py tidak error
    def __init__(self, bot_instance=None):
        # KONFIGURASI API (Gunakan API Key kamu)
        self.base_url = "https://moltyroyale.com"
        self.api_key = "21ae88b7-7323-4133-8f36-6bb831aa9590"
        self.headers = {"X-API-Key": self.api_key}
        
        self.bot = bot_instance
        self.game_id = None
        self.agent_id = None
        self.last_pos = {'regionId': None}
        self.stuck_count = 0
        
        # DATABASE JAWABAN GUARDIAN
        self.riddle_db = {
            "france": "Paris",
            "2 + 2": "4",
            "sky": "Blue",
            "answer to everything": "42"
        }

    def start_game(self):
        try:
            # 1. Cari Game
            resp = requests.get(f"{self.base_url}/games?status=waiting", timeout=10)
            if resp.status_code != 200: return
            
            games = resp.json().get("data", [])
            if not games: return
            
            # Ambil ID game pertama yang tersedia
            self.game_id = games[0]["id"] if isinstance(games, list) else games["id"]
            
            # 2. Registrasi
            res = requests.post(
                f"{self.base_url}/games/{self.game_id}/agents/register",
                headers=self.headers,
                json={"name": "AggressiveBot"},
                timeout=10
            )
            
            data = res.json().get("data")
            if data:
                self.agent_id = data["id"]
                print(f"BERHASIL JOIN MATCH! ID: {self.agent_id}")
        except Exception as e:
            print(f"Error start_game: {e}")

    def run_logic(self, game_state=None):
        # Jika game_state tidak dikirim dari main.py, kita ambil sendiri
        if not game_state:
            try:
                resp = requests.get(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/state", 
                                    headers=self.headers, timeout=10)
                game_state = resp.json().get("data")
            except: return

        if not game_state or not game_state["self"]["isAlive"]:
            return

        self_data = game_state["self"]
        curr_region = game_state["currentRegion"]
        inv = self_data.get('inventory', [])
        ep = self_data.get('ep', 0)
        hp = self_data.get('hp', 100)

        # --- A. FREE ACTIONS ---
        # 1. Anti-Curse (Cek Whisper)
        for msg in game_state.get("recentMessages", []):
            if msg["senderId"] != self.agent_id and msg.get("type") == "whisper":
                text = msg["message"].lower()
                ans = next((a for q, a in self.riddle_db.items() if q in text), "Cooperating.")
                self.send_whisper(msg["senderId"], ans)

        # 2. Auto Pickup (Limit 8 slot)
        if len(inv) < 8:
            for itm in game_state.get("visibleItems", []):
                if itm["regionId"] == self_data["regionId"]:
                    self.post_action({"type": "pickup", "itemId": itm["item"]["id"]}, "Looting")

        # 3. Auto Equip Senjata Terbaik
        weapons = [i for i in inv if i.get("category") == "weapon"]
        if weapons:
            best = max(weapons, key=lambda w: w.get('atkBonus', 0))
            curr_atk = (self_data.get("equippedWeapon") or {}).get("atkBonus", 0)
            if best['atkBonus'] > curr_atk:
                self.post_action({"type": "equip", "itemId": best['id']}, "Equipping best weapon")

        # --- B. MAIN ACTIONS ---
        action = {"type": "explore"}
        reason = "Patrolling area"

        # 1. Prioritas: Lari dari Death Zone
        if curr_region.get('isDeathZone'):
            exits = curr_region.get("connections", [])
            action = {"type": "move", "regionId": exits[0] if exits else None}
            reason = "Escaping Death Zone!"
        
        # 2. Prioritas: Healing
        elif hp < 30:
            meds = next((i for i in inv if i.get("category") == "recovery"), None)
            if meds: action = {"type": "use_item", "itemId": meds["id"]}
            reason = "Critical HP: Healing"

        # 3. Prioritas: Rest jika EP Low
        elif ep < 2:
            action = {"type": "rest"}
            reason = "Recovering Energy"

        # 4. Prioritas: Serang
        else:
            enemies = [a for a in game_state.get("visibleAgents", []) if a["isAlive"]]
            if enemies:
                target = min(enemies, key=lambda a: a['hp'])
                action = {"type": "attack", "targetId": target["id"], "targetType": "agent"}
                reason = "Attacking weak player"
            else:
                monsters = game_state.get("visibleMonsters", [])
                if monsters:
                    # Cari Guardian dulu untuk sMoltz besar
                    guard = next((m for m in monsters if "Guardian" in m.get("type", "")), monsters[0])
                    action = {"type": "attack", "targetId": guard["id"], "targetType": "monster"}
                    reason = "Hunting for sMoltz"

        self.post_action(action, reason)

    def post_action(self, action, thought):
        try:
            requests.post(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/action", 
                          headers=self.headers, json={"action": action, "thought": {"reasoning": thought}}, timeout=5)
        except: pass

    def send_whisper(self, target_id, message):
        try:
            requests.post(f"{self.base_url}/games/{self.game_id}/agents/{self.agent_id}/action",
                          headers=self.headers, json={"action": {"type": "whisper", "targetId": target_id, "message": message}}, timeout=5)
        except: pass
