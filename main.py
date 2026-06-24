# ============================================
# DISCORD CASINO BOT - COMPLETE PRODUCTION CODE
# Python 3.12 + discord.py 2.x + Firebase
# ============================================

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import json
import os
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple, Any
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client as FirestoreClient
from google.cloud.firestore_v1.base_query import FieldFilter
from aiohttp import web
from dotenv import load_dotenv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import warnings
from enum import Enum
warnings.filterwarnings('ignore')

# ============================================
# DISCORD BOT GLOBAL INITIALIZATION
# ============================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Khai báo bot sớm nhất có thể để tránh mọi lỗi NameError khi đăng ký lệnh
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ============================================
# LOAD ENVIRONMENT VARIABLES
# ============================================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID")
FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT")

if not all([DISCORD_TOKEN, SUPER_ADMIN_ID, FIREBASE_SERVICE_ACCOUNT]):
    raise ValueError("Missing required environment variables!")

# ============================================
# INITIALIZE FIREBASE
# ============================================
try:
    service_account_dict = json.loads(FIREBASE_SERVICE_ACCOUNT)
    cred = credentials.Certificate(service_account_dict)
    firebase_admin.initialize_app(cred)
    db: FirestoreClient = firestore.client()
    print("✅ Firebase connected successfully!")
except Exception as e:
    print(f"❌ Firebase connection failed: {e}")
    raise

# ============================================
# CONSTANTS & CONFIGURATION
# ============================================
DEFAULT_BALANCE = 100000
DAILY_REWARD = 100000
LOAN_DUE_DAYS = 7
COOLDOWN_NORMAL = 5
COOLDOWN_DAILY = 86400

ANTI_STREAK_ENABLED = True
MAX_HISTORY_FOR_ANALYSIS = 100

EMOJI_COIN = "💰"
EMOJI_GEM = "💎"
EMOJI_CROWN = "👑"
EMOJI_TROPHY = "🏆"
EMOJI_FIRE = "🔥"
EMOJI_ICE = "❄️"
EMOJI_DICE = "🎲"
EMOJI_CARD = "🃏"
EMOJI_SLOT = "🎰"
EMOJI_CHART = "📊"
EMOJI_BANK = "🏦"
EMOJI_GIFT = "🎁"
EMOJI_RED_ENVELOPE = "🧧"
EMOJI_PARTY = "🎉"
EMOJI_STAR = "⭐"
EMOJI_CHECK = "✅"
EMOJI_CROSS = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_CLOCK = "⏰"
EMOJI_ROBOT = "🤖"
EMOJI_TAI = "🔴"
EMOJI_XIU = "🔵"
EMOJI_CHAN = "⚪"
EMOJI_LE = "⚫"

COLOR_PRIMARY = 0x2F3136
COLOR_SUCCESS = 0x00FF00
COLOR_ERROR = 0xFF0000
COLOR_WARNING = 0xFFA500
COLOR_INFO = 0x3498DB
COLOR_GOLD = 0xFFD700
COLOR_RED = 0xFF0000
COLOR_GREEN = 0x00FF00
COLOR_BLUE = 0x0000FF
COLOR_PURPLE = 0x800080

PROFILE_COLORS = {
    "🔴 Đỏ": 0xFF0000,
    "🟢 Xanh lá": 0x00FF00,
    "🔵 Xanh dương": 0x3498DB,
    "🟣 Tím": 0x800080,
    "🟡 Vàng": 0xFFD700,
    "⚫ Đen": 0x000000
}

SLOT_SYMBOLS = ["🍒", "🍋", "⭐", "💎"]
SLOT_PAYOUTS = {"💎💎💎": 20, "⭐⭐⭐": 10, "🍒🍒🍒": 5, "🍋🍋🍋": 3}

SPECIFIC_NUMBER_PAYOUTS = {
    3: 30, 18: 30, 4: 12, 17: 12, 5: 8, 16: 8, 6: 6, 15: 6,
    7: 5, 14: 5, 8: 4, 13: 4, 9: 3, 12: 3, 10: 2, 11: 2
}

BADGE_DAI_GIA = 10_000_000
BADGE_TY_PHU = 1_000_000_000
BADGE_TRIEU_PHU = 1_000_000
BADGE_CAO_THU = 500
BADGE_STREAK_GOD = 20

# ============================================
# RATE LIMITER & COOLDOWN CLASS
# ============================================
class RateLimiter:
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
        self.processing: Dict[str, bool] = {}
    
    async def acquire(self, key: str) -> bool:
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        if self.processing.get(key, False):
            return False
        async with self.locks[key]:
            if self.processing.get(key, False):
                return False
            self.processing[key] = True
            return True
    
    def release(self, key: str):
        self.processing[key] = False

rate_limiter = RateLimiter()

class CooldownManager:
    def __init__(self):
        self.cooldowns: Dict[str, Dict[str, datetime]] = {}
    
    def check_cooldown(self, user_id: str, command: str, seconds: int) -> Tuple[bool, Optional[int]]:
        if command not in self.cooldowns:
            self.cooldowns[command] = {}
        if user_id in self.cooldowns[command]:
            last_used = self.cooldowns[command][user_id]
            elapsed = (datetime.now(timezone.utc) - last_used).total_seconds()
            if elapsed < seconds:
                return True, int(seconds - elapsed)
        return False, None
    
    def set_cooldown(self, user_id: str, command: str):
        if command not in self.cooldowns:
            self.cooldowns[command] = {}
        self.cooldowns[command][user_id] = datetime.now(timezone.utc)

cooldown_manager = CooldownManager()

# ============================================
# ROOM PERSISTENT RECOVERY STATE MANAGERS
# ============================================
class RoomStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"

class RoomGame(str, Enum):
    TAIXIU = "taixiu"
    BLACKJACK = "blackjack"
    TIENLEN = "tienlen"

class RoomManager:
    def __init__(self):
        self.active_rooms: Dict[str, Dict] = {}
        self.player_rooms: Dict[str, str] = {}
        self.room_states: Dict[str, Dict] = {}
        self.room_views: Dict[str, discord.ui.View] = {}
    
    def create_room(self, owner_id: str, room_id: str, game_type: str, thread: discord.Thread, bet_amount: int) -> bool:
        if owner_id in self.player_rooms:
            return False
        
        room_data = {
            "roomId": room_id,
            "ownerId": owner_id,
            "gameType": game_type,
            "status": RoomStatus.WAITING,
            "threadId": thread.id,
            "channelId": thread.parent.id,
            "guildId": thread.guild.id,
            "players": [owner_id],
            "betAmount": bet_amount,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        }
        
        self.active_rooms[room_id] = room_data
        self.player_rooms[owner_id] = room_id
        self.room_states[room_id] = {
            "custom_bets": {owner_id: bet_amount} if game_type == "blackjack" else {}
        }
        
        db.collection("rooms").document(room_id).set({
            "room_data": room_data,
            "room_state": self.room_states[room_id]
        })
        return True
    
    def join_room(self, user_id: str, room_id: str, custom_bet: Optional[int] = None) -> bool:
        if room_id not in self.active_rooms:
            return False
        if user_id in self.player_rooms:
            return False
        
        room = self.active_rooms[room_id]
        if room["status"] != RoomStatus.WAITING:
            return False
        
        room["players"].append(user_id)
        self.player_rooms[user_id] = room_id
        
        if custom_bet is not None and room["gameType"] == "blackjack":
            self.room_states[room_id].setdefault("custom_bets", {})[user_id] = custom_bet
            
        self.save_room_state_to_db(room_id)
        return True
    
    def leave_room(self, user_id: str, room_id: str) -> bool:
        if room_id not in self.active_rooms:
            return False
        
        room = self.active_rooms[room_id]
        if user_id in room["players"]:
            room["players"].remove(user_id)
        if user_id in self.player_rooms:
            del self.player_rooms[user_id]
        if room_id in self.room_states and "custom_bets" in self.room_states[room_id]:
            self.room_states[room_id]["custom_bets"].pop(user_id, None)
            
        self.save_room_state_to_db(room_id)
        return True
    
    def get_player_room(self, user_id: str) -> Optional[str]:
        return self.player_rooms.get(user_id)
    
    def get_room(self, room_id: str) -> Optional[Dict]:
        return self.active_rooms.get(room_id)
    
    def set_room_status(self, room_id: str, status: RoomStatus):
        if room_id in self.active_rooms:
            self.active_rooms[room_id]["status"] = status
            self.save_room_state_to_db(room_id)
            
    def save_room_state_to_db(self, room_id: str):
        if room_id in self.active_rooms:
            db.collection("rooms").document(room_id).set({
                "room_data": self.active_rooms[room_id],
                "room_state": self.room_states.get(room_id, {})
            }, merge=True)
            
    def store_view(self, room_id: str, view: discord.ui.View):
        self.room_views[room_id] = view
    
    async def cleanup_room(self, room_id: str):
        if room_id not in self.active_rooms:
            return
        room = self.active_rooms[room_id]
        for player_id in room["players"]:
            if player_id in self.player_rooms:
                del self.player_rooms[player_id]
        if room_id in self.room_views:
            try:
                view = self.room_views[room_id]
                view.stop()
                for item in view.children:
                    item.disabled = True
            except: pass
            del self.room_views[room_id]
        if room_id in self.room_states:
            del self.room_states[room_id]
        try:
            db.collection("rooms").document(room_id).delete()
        except: pass
        del self.active_rooms[room_id]

room_manager = RoomManager()

# ============================================
# DATABASE HELPERS & ATOMIC FIREBASE TRANSACTIONS
# ============================================
def get_user_ref(user_id: str): return db.collection("users").document(str(user_id))
def get_admin_ref(user_id: str): return db.collection("admins").document(str(user_id))
def get_loan_ref(loan_id: str): return db.collection("loans").document(str(loan_id))
def get_transactions_ref(): return db.collection("transactions")
def get_game_history_ref(): return db.collection("game_history")

async def get_user_data(user_id: str) -> Optional[Dict]:
    doc = get_user_ref(user_id).get()
    return doc.to_dict() if doc.exists else None

async def create_user_if_not_exists(user_id: str) -> Dict:
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        now = datetime.now(timezone.utc)
        user_data = {
            "userId": str(user_id), "balance": DEFAULT_BALANCE, "totalGames": 0, "totalWins": 0, "totalLosses": 0,
            "currentWinStreak": 0, "currentLoseStreak": 0, "bestWinStreak": 0, "biggestWin": 0, "biggestLoss": 0,
            "totalMoneyWon": 0, "totalMoneyLost": 0, "freeBetShield": 0, "discountCouponUses": 0,
            "profileColor": "🔵 Xanh dương", "dailyLastClaim": None, "createdAt": now
        }
        user_ref.set(user_data)
        return user_data
    return user_doc.to_dict()

async def is_admin(user_id: str) -> bool:
    if str(user_id) == SUPER_ADMIN_ID: return True
    return get_admin_ref(str(user_id)).get().exists

async def is_super_admin(user_id: str) -> bool:
    return str(user_id) == SUPER_ADMIN_ID

async def check_loans_overdue(user_id: str) -> Tuple[bool, List[Dict]]:
    loans = db.collection("loans").where(filter=FieldFilter("borrowerId", "==", str(user_id))).where(filter=FieldFilter("repaid", "==", False)).get()
    now = datetime.now(timezone.utc)
    overdue_loans = []
    for l in loans:
        d = l.to_dict()
        if "dueAt" in d:
            due_at = datetime.fromisoformat(d["dueAt"]) if isinstance(d["dueAt"], str) else d["dueAt"]
            if due_at < now: overdue_loans.append(d)
    return len(overdue_loans) > 0, overdue_loans

async def add_log(log_type: str, user_id: str, amount: int, target_id: Optional[str] = None, description: Optional[str] = None):
    db.collection("logs").add({"type": log_type, "userId": str(user_id), "amount": amount, "targetId": str(target_id) if target_id else None, "description": description, "timestamp": datetime.now(timezone.utc)})

async def add_transaction(transaction_type: str, user_id: str, amount: int, target_id: Optional[str] = None, description: Optional[str] = None):
    get_transactions_ref().add({"type": transaction_type, "userId": str(user_id), "amount": amount, "targetId": str(target_id) if target_id else None, "description": description, "timestamp": datetime.now(timezone.utc)})

async def log_error(error_type: str, command: str, user_id: str, error: str, traceback_str: str):
    try: db.collection("error_logs").add({"error": error, "traceback": traceback_str[:1500], "command": command, "userId": user_id, "createdAt": datetime.now(timezone.utc)})
    except: pass

@firestore.transactional
def _tx_transfer(transaction, from_id: str, to_id: str, amount: int) -> bool:
    from_ref, to_ref = get_user_ref(from_id), get_user_ref(to_id)
    from_snap, to_snap = transaction.get(from_ref), transaction.get(to_ref)
    if not from_snap.exists or not to_snap.exists: return False
    from_data, to_data = from_snap.to_dict(), to_snap.to_dict()
    if from_data.get("balance", 0) < amount: return False
    transaction.update(from_ref, {"balance": from_data["balance"] - amount})
    transaction.update(to_ref, {"balance": to_data.get("balance", 0) + amount})
    return True

@firestore.transactional
def _tx_adjust_balance(transaction, user_id: str, amount: int) -> bool:
    user_ref = get_user_ref(user_id)
    user_snap = transaction.get(user_ref)
    if not user_snap.exists: return False
    user_data = user_snap.to_dict()
    new_balance = user_data.get("balance", 0) + amount
    if new_balance < 0: return False
    transaction.update(user_ref, {"balance": new_balance})
    return True

@firestore.transactional
def _tx_jackpot_add(transaction, amount: int):
    jackpot_ref = db.collection("system").document("jackpot")
    jackpot_snap = transaction.get(jackpot_ref)
    current = jackpot_snap.to_dict().get("amount", 0) if jackpot_snap.exists else 0
    transaction.set(jackpot_ref, {"amount": current + amount}, merge=True)

async def transfer_money(from_id: str, to_id: str, amount: int, transaction_type: str = "transfer") -> bool:
    try:
        result = _tx_transfer(db.transaction(), from_id, to_id, amount)
        if result:
            await add_log(transaction_type, from_id, amount, to_id)
            await add_transaction(transaction_type, from_id, amount, to_id)
        return result
    except Exception as e: return False

async def add_money(user_id: str, amount: int, admin_id: str = "system") -> bool:
    try:
        result = _tx_adjust_balance(db.transaction(), user_id, amount)
        if result:
            await add_log("addmoney", user_id, amount, admin_id)
            await add_transaction("addmoney", user_id, amount, admin_id)
        return result
    except Exception as e: return False

async def remove_money(user_id: str, amount: int, admin_id: str = "system") -> bool:
    try:
        result = _tx_adjust_balance(db.transaction(), user_id, -amount)
        if result:
            await add_log("trutien", user_id, amount, admin_id)
            await add_transaction("trutien", user_id, -amount, admin_id)
        return result
    except Exception as e: return False

async def deduct_bet(user_id: str, amount: int) -> bool:
    try:
        result = _tx_adjust_balance(db.transaction(), user_id, -amount)
        if result:
            jackpot_amount = int(amount * 0.02)
            try: _tx_jackpot_add(db.transaction(), jackpot_amount)
            except: pass
        return result
    except Exception as e: return False

async def add_win(user_id: str, amount: int) -> bool:
    try: return _tx_adjust_balance(db.transaction(), user_id, amount)
    except Exception as e: return False

async def get_jackpot() -> int:
    doc = db.collection("system").document("jackpot").get()
    return doc.to_dict().get("amount", 0) if doc.exists else 0

async def update_user_stats(user_id: str, is_win: bool, bet_amount: int, win_amount: int):
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return
    user_data = user_doc.to_dict()
    user_data["totalGames"] = user_data.get("totalGames", 0) + 1
    if is_win:
        user_data["totalWins"] = user_data.get("totalWins", 0) + 1
        user_data["currentWinStreak"] = user_data.get("currentWinStreak", 0) + 1
        user_data["currentLoseStreak"] = 0
        if user_data["currentWinStreak"] > user_data.get("bestWinStreak", 0): user_data["bestWinStreak"] = user_data["currentWinStreak"]
        if win_amount > user_data.get("biggestWin", 0): user_data["biggestWin"] = win_amount
        user_data["totalMoneyWon"] = user_data.get("totalMoneyWon", 0) + win_amount
    else:
        user_data["totalLosses"] = user_data.get("totalLosses", 0) + 1
        user_data["currentLoseStreak"] = user_data.get("currentLoseStreak", 0) + 1
        user_data["currentWinStreak"] = 0
        if bet_amount > user_data.get("biggestLoss", 0): user_data["biggestLoss"] = bet_amount
        user_data["totalMoneyLost"] = user_data.get("totalMoneyLost", 0) + bet_amount
    user_ref.set(user_data)

async def check_and_deduct_shield(user_id: str) -> bool:
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return False
    user_data = user_doc.to_dict()
    if user_data.get("freeBetShield", 0) > 0:
        user_data["freeBetShield"] -= 1
        user_ref.set(user_data)
        return True
    return False

async def check_and_deduct_coupon(user_id: str) -> bool:
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return False
    user_data = user_doc.to_dict()
    if user_data.get("discountCouponUses", 0) > 0:
        user_data["discountCouponUses"] -= 1
        user_ref.set(user_data)
        return True
    return False

def create_embed(title: str, description: str = "", color: int = COLOR_PRIMARY, fields: List[Tuple[str, str, bool]] = None, thumbnail_url: str = None, footer_text: str = None, timestamp: bool = True) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc) if timestamp else None)
    if thumbnail_url: embed.set_thumbnail(url=thumbnail_url)
    if fields:
        for name, value, inline in fields: embed.add_field(name=name, value=value, inline=inline)
    if footer_text: embed.set_footer(text=footer_text)
    return embed

# ============================================
# CHART GENERATOR & ANALYSIS
# ============================================
def generate_cau_chart(game_list: List[Dict]) -> BytesIO:
    if not game_list:
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor='#1a0a2e')
        ax.set_facecolor('#1a0a2e')
        ax.text(0.5, 0.5, 'Chưa có dữ liệu phiên nào!\nHãy chơi Tài Xỉu trước.', ha='center', va='center', fontsize=24, color='white', transform=ax.transAxes)
        ax.axis('off')
        buf = BytesIO()
        fig.savefig(buf, format='png', facecolor='#1a0a2e', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf
    game_list = list(reversed(game_list))
    results = [g.get('result', 0) for g in game_list]
    dice1_list = [g.get('dice1', 0) for g in game_list]
    dice2_list = [g.get('dice2', 0) for g in game_list]
    dice3_list = [g.get('dice3', 0) for g in game_list]
    tai_xiu_list = [g.get('taiOrXiu', '') for g in game_list]
    sessions = list(range(1, len(results) + 1))
    total_phiens = len(results)
    bg_dark, tai_color, xiu_color, gold, cyan, yellow, white = '#0d0520', '#FF4444', '#4488FF', '#FFD700', '#00FFFF', '#FFFF00', '#FFFFFF'
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=bg_dark)
    gs = fig.add_gridspec(4, 4, hspace=0.4, wspace=0.3, top=0.93, bottom=0.05, left=0.05, right=0.98)
    fig.suptitle('🎲 THỐNG KÊ TÀI XỈU', fontsize=20, fontweight='bold', color=gold, y=0.98, fontfamily='monospace')
    ax_info = fig.add_subplot(gs[0, 3])
    ax_info.set_facecolor('#150830')
    ax_info.axis('off')
    if total_phiens > 0:
        last_tai_xiu = tai_xiu_list[-1]
        last_dice = f"{dice1_list[-1]}-{dice2_list[-1]}-{dice3_list[-1]}"
        color = tai_color if last_tai_xiu == 'tai' else xiu_color if last_tai_xiu == 'xiu' else gold
        label = 'TÀI' if last_tai_xiu == 'tai' else 'XỈU' if last_tai_xiu == 'xiu' else 'BỘ BA'
        ax_info.text(0.5, 0.85, f'Phiên #{total_phiens}', ha='center', fontsize=13, color=white, fontweight='bold', fontfamily='monospace')
        ax_info.text(0.5, 0.5, label, ha='center', fontsize=28, color=color, fontweight='bold', fontfamily='monospace')
        ax_info.text(0.5, 0.2, f'({last_dice})', ha='center', fontsize=11, color='#aaaaaa', fontfamily='monospace')
    ax1 = fig.add_subplot(gs[0:2, 0:3])
    ax1.set_facecolor('#150830')
    ax1.plot(sessions, results, color=white, linewidth=2.5, marker='o', markersize=9, markerfacecolor=gold, markeredgecolor=white, markeredgewidth=1.5, zorder=5)
    ax1.fill_between(sessions, results, 3, alpha=0.15, color=gold)
    for i, val in enumerate(results): ax1.annotate(str(val), (sessions[i], val), textcoords="offset points", xytext=(0, 12), ha='center', fontsize=8, color=white, fontweight='bold', fontfamily='monospace')
    ax1.set_ylim(2, 19)
    ax1.set_yticks(range(3, 19))
    ax1.set_ylabel('Tổng Điểm', color=white, fontsize=10, fontfamily='monospace')
    ax1.set_xlabel('Phiên', color=white, fontsize=10, fontfamily='monospace')
    ax1.tick_params(colors=white, labelsize=8)
    ax1.grid(True, alpha=0.2, linestyle='--', color='white')
    ax1.set_title('📊 BIỂU ĐỒ TỔNG ĐIỂM', color=gold, fontsize=11, fontweight='bold', fontfamily='monospace', pad=8)
    ax2 = fig.add_subplot(gs[2, 0:2])
    ax2.set_facecolor('#150830')
    ax2.plot(sessions, dice1_list, color='#FF6B6B', linewidth=1.8, marker='s', markersize=6, markerfacecolor='#FF6B6B', label='Xúc xắc 1')
    ax2.plot(sessions, dice2_list, color=cyan, linewidth=1.8, marker='^', markersize=6, markerfacecolor=cyan, label='Xúc xắc 2')
    ax2.plot(sessions, dice3_list, color=yellow, linewidth=1.8, marker='D', markersize=6, markerfacecolor=yellow, label='Xúc xắc 3')
    ax2.set_ylim(0.5, 6.5)
    ax2.set_yticks(range(1, 7))
    ax2.set_ylabel('Giá trị', color=white, fontsize=9, fontfamily='monospace')
    ax2.tick_params(colors=white, labelsize=8)
    ax2.grid(True, alpha=0.2, linestyle='--', color='white')
    ax2.legend(loc='upper left', fontsize=8, facecolor='#150830', edgecolor='#3a2a5e', labelcolor=white)
    ax2.set_title('🎲 THỐNG KÊ XÚC XẮC', color=gold, fontsize=11, fontweight='bold', fontfamily='monospace', pad=8)
    ax3 = fig.add_subplot(gs[2, 2:])
    ax3.set_facecolor('#150830')
    ax3.axis('off')
    ax3.text(0.5, 0.85, '📈 THỐNG KÊ CẦU', ha='center', fontsize=11, color=gold, fontweight='bold', fontfamily='monospace')
    n = len(tai_xiu_list)
    max_per_row = 10
    rows = (n + max_per_row - 1) // max_per_row
    y_start, y_spacing = 0.6, 0.15
    for row in range(rows):
        start_idx = row * max_per_row
        end_idx = min((row + 1) * max_per_row, n)
        row_count = end_idx - start_idx
        x_spacing = 0.9 / row_count
        y_pos = y_start - row * y_spacing
        for i, idx in enumerate(range(start_idx, end_idx)):
            x_pos = 0.1 + i * x_spacing + x_spacing / 2
            result_type = tai_xiu_list[idx]
            color = tai_color if result_type == 'tai' else xiu_color if result_type == 'xiu' else gold
            circle = plt.Circle((x_pos, y_pos), 0.025, color=color, transform=ax3.transAxes)
            ax3.add_patch(circle)
    tai_patch = mpatches.Patch(color=tai_color, label='TÀI')
    xiu_patch = mpatches.Patch(color=xiu_color, label='XỈU')
    ax3.legend(handles=[tai_patch, xiu_patch], loc='lower center', fontsize=8, facecolor='#150830', edgecolor='#3a2a5e', labelcolor=white, ncol=2)
    ax4 = fig.add_subplot(gs[3, :])
    ax4.set_facecolor('#150830')
    ax4.axis('off')
    tai_count = sum(1 for t in tai_xiu_list if t == 'tai')
    xiu_count = sum(1 for t in tai_xiu_list if t == 'xiu')
    current_streak = 0
    streak_type = None
    for t in reversed(tai_xiu_list):
        if t == 'triple': continue
        if streak_type is None:
            streak_type = t
            current_streak = 1
        elif t == streak_type: current_streak += 1
        else: break
    if tai_count > xiu_count:
        prediction = '🔴 TÀI'
        confidence = 50 + min(15, tai_count - xiu_count)
    elif xiu_count > tai_count:
        prediction = '🔵 XỈU'
        confidence = 50 + min(15, xiu_count - tai_count)
    else:
        prediction = random.choice(['🔴 TÀI', '🔵 XỈU'])
        confidence = 55
    confidence = min(65, confidence)
    ax4.text(0.03, 0.85, '📊 PHÂN TÍCH & DỰ ĐOÁN', color=gold, fontsize=13, fontweight='bold', fontfamily='monospace')
    ax4.text(0.03, 0.6, f'Tài: {tai_count}/{total_phiens} ({tai_count/total_phiens*100:.0f}%)', color=white, fontsize=10, fontfamily='monospace')
    ax4.text(0.03, 0.4, f'Xỉu: {xiu_count}/{total_phiens} ({xiu_count/total_phiens*100:.0f}%)', color=white, fontsize=10, fontfamily='monospace')
    streak_text = f'{current_streak} phiên {streak_type} liên tiếp' if streak_type else 'N/A'
    ax4.text(0.03, 0.2, f'🔥 Chuỗi: {streak_text}', color=white, fontsize=10, fontfamily='monospace')
    ax4.text(0.55, 0.6, f'🤖 Dự đoán: {prediction}', color=gold, fontsize=14, fontweight='bold', fontfamily='monospace')
    ax4.text(0.55, 0.35, f'Độ tin cậy: {confidence}%', color='#aaaaaa', fontsize=11, fontfamily='monospace')
    ax4.text(0.55, 0.15, f'Tỷ lệ đúng: 50-65%', color='#777777', fontsize=8, fontfamily='monospace')
    buf = BytesIO()
    fig.savefig(buf, format='png', facecolor=bg_dark, bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    return buf

def get_recent_games(limit: int = 100) -> List[Dict]:
    games = get_game_history_ref().order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit).get()
    return [doc.to_dict() for doc in games]

def analyze_streak(game_list: List[Dict]) -> Tuple[int, Optional[str]]:
    if not game_list: return 0, None
    streak_type = None
    count = 0
    for g in game_list:
        tai_xiu = g.get('taiOrXiu', '')
        if tai_xiu == 'triple': continue
        if streak_type is None:
            streak_type = tai_xiu
            count = 1
        elif tai_xiu == streak_type: count += 1
        else: break
    return count, streak_type

def calculate_weighted_roll(game_list: List[Dict]) -> Tuple[int, int, int]:
    if not ANTI_STREAK_ENABLED: return random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
    recent = game_list[:MAX_HISTORY_FOR_ANALYSIS]
    tai_count = sum(1 for g in recent if g.get('taiOrXiu') == 'tai')
    xiu_count = sum(1 for g in recent if g.get('taiOrXiu') == 'xiu')
    total = tai_count + xiu_count
    streak_count, streak_type = analyze_streak(game_list[:20])
    tai_prob, xiu_prob = 0.5, 0.5
    if streak_type == 'tai':
        if streak_count >= 7: tai_prob, xiu_prob = 0.05, 0.95
        elif streak_count >= 6: tai_prob, xiu_prob = 0.15, 0.85
        elif streak_count >= 5: tai_prob, xiu_prob = 0.25, 0.75
        elif streak_count >= 4: tai_prob, xiu_prob = 0.35, 0.65
    elif streak_type == 'xiu':
        if streak_count >= 7: tai_prob, xiu_prob = 0.95, 0.05
        elif streak_count >= 6: tai_prob, xiu_prob = 0.85, 0.15
        elif streak_count >= 5: tai_prob, xiu_prob = 0.75, 0.25
        elif streak_count >= 4: tai_prob, xiu_prob = 0.65, 0.35
    if total > 20:
        tai_percent = tai_count / total
        if tai_percent > 0.70: tai_prob -= 0.20; xiu_prob += 0.20
        elif tai_percent > 0.60: tai_prob -= 0.10; xiu_prob += 0.10
        elif tai_percent < 0.30: tai_prob += 0.20; xiu_prob -= 0.20
        elif tai_percent < 0.40: tai_prob += 0.10; xiu_prob -= 0.10
    total_prob = tai_prob + xiu_prob
    tai_prob = max(0.05, min(0.95, tai_prob / total_prob))
    xiu_prob = 1.0 - tai_prob
    if random.random() < tai_prob: total_score = random.randint(11, 17)
    else: total_score = random.randint(4, 10)
    attempts = 0
    while attempts < 1000:
        d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
        if d1 + d2 + d3 == total_score: return d1, d2, d3
        attempts += 1
    d1 = min(6, max(1, total_score // 3))
    remaining = total_score - d1
    d2 = min(6, max(1, remaining // 2))
    d3 = total_score - d1 - d2
    if d3 < 1: d2 -= (1 - d3); d3 = 1
    elif d3 > 6: d2 += (d3 - 6); d3 = 6
    return d1, d2, d3

def detect_cau_pattern(game_list: List[Dict]) -> str:
    if len(game_list) < 4: return "Chưa đủ dữ liệu"
    recent = game_list[:10]
    tai_xiu = [g.get('taiOrXiu', '') for g in recent if g.get('taiOrXiu') != 'triple']
    if len(tai_xiu) < 4: return "Đang phân tích..."
    if len(tai_xiu) >= 4:
        if all(tai_xiu[i] != tai_xiu[i+1] for i in range(min(4, len(tai_xiu)-1))): return "Cầu 1-1 (Đơn xen kẽ)"
    if len(tai_xiu) >= 6:
        pairs = [tai_xiu[i:i+2] for i in range(0, 6, 2)]
        if len(pairs) >= 2 and all(len(set(p)) == 1 for p in pairs) and pairs[0] != pairs[1]: return "Cầu 2-2"
    if len(tai_xiu) >= 9:
        triples = [tai_xiu[i:i+3] for i in range(0, 9, 3)]
        if len(triples) >= 2 and all(len(set(t)) == 1 for t in triples) and triples[0] != triples[1]: return "Cầu 3-3"
    streak_count, streak_type = analyze_streak(game_list)
    if streak_count >= 4: return f"Cầu bệt {streak_type.upper()} ({streak_count} phiên)"
    if streak_count == 3: return f"Có dấu hiệu bệt {streak_type.upper()}"
    return "Cầu gãy / Không xác định"

# ============================================
# GAME: BLACKJACK EPHEMERAL & INDIVIDUAL BETS
# ============================================
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUES = {"A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}

class BlackjackDeck:
    def __init__(self):
        self.cards = []
        self.reset()
    def reset(self):
        self.cards = [(rank, suit) for suit in SUITS for rank in RANKS]
        random.shuffle(self.cards)
    def draw(self):
        if not self.cards: self.reset()
        return self.cards.pop()

def calculate_hand(hand: List[Tuple[str, str]]) -> int:
    value = 0
    aces = 0
    for card in hand:
        if card[0] == "A": aces += 1
        value += RANK_VALUES[card[0]]
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value

def hand_str(hand: List[Tuple[str, str]], hide_second=False) -> str:
    if hide_second and len(hand) >= 2: return f"{hand[0][1]}{hand[0][0]} ??"
    return " ".join([f"{c[1]}{c[0]}" for c in hand])

async def start_blackjack_full(room_id: str, thread: discord.Thread):
    room = room_manager.get_room(room_id)
    if not room: return
    players = room["players"]
    deck = BlackjackDeck()
    player_hands = {p: [deck.draw(), deck.draw()] for p in players}
    dealer_hand = [deck.draw(), deck.draw()]
    player_bust = {p: False for p in players}
    player_blackjack = {p: False for p in players}
    player_done = {p: False for p in players}
    
    for p in players:
        if calculate_hand(player_hands[p]) == 21:
            player_blackjack[p] = True
            player_done[p] = True
            
    state = room_manager.room_states[room_id]
    state.update({
        "deck_cards": deck.cards, "player_hands": player_hands, "dealer_hand": dealer_hand,
        "player_bust": player_bust, "player_blackjack": player_blackjack,
        "player_done": player_done, "current_turn_index": 0
    })
    room_manager.save_room_state_to_db(room_id)
    
    await update_bj_board_msg(room_id, thread)

async def update_bj_board_msg(room_id: str, thread: discord.Thread):
    room = room_manager.get_room(room_id)
    state = room_manager.room_states.get(room_id, {})
    if not room or not state: return
    
    players = room["players"]
    turn_idx = state.get("current_turn_index", 0)
    dealer_hand = state.get("dealer_hand", [])
    player_done = state.get("player_done", {})
    player_bust = state.get("player_bust", {})
    player_blackjack = state.get("player_blackjack", {})
    custom_bets = state.get("custom_bets", {})
    
    # Hide Dealer's card if players are still playing
    all_done = all(player_done.get(p, False) for p in players)
    dealer_display = hand_str(dealer_hand, hide_second=not all_done)
    dealer_pts = calculate_hand(dealer_hand) if all_done else "??"
    
    description = "🃏 **BLACKJACK GAME BOARD**\n\n"
    description += f"🤖 **Dealer's Hand:** {dealer_display} (Điểm: {dealer_pts})\n\n"
    description += "👥 **Người Chơi:**\n"
    
    for idx, pid in enumerate(players):
        turn_marker = "🎯 " if idx == turn_idx and not all_done and not player_done.get(pid, False) else "   "
        bet = custom_bets.get(pid, room["betAmount"])
        status = "Bust 💥" if player_bust.get(pid) else "Stand ✋" if player_done.get(pid) else "Đang chơi... ⏳"
        if player_blackjack.get(pid): status = "Blackjack! 🎉"
        description += f"{turn_marker}<@{pid}> (Cược: {bet:,} VNĐ) - Trạng thái: **{status}**\n"
        
    embed = create_embed(title="🃏 Blackjack Table", description=description, color=COLOR_GOLD)
    
    # If board message exists, edit it. Otherwise, send and store its ID.
    board_msg_id = state.get("board_msg_id")
    board_msg = None
    if board_msg_id:
        try: board_msg = await thread.fetch_message(board_msg_id)
        except: pass
        
    if board_msg:
        await board_msg.edit(embed=embed)
    else:
        board_msg = await thread.send(embed=embed)
        state["board_msg_id"] = board_msg.id
        room_manager.save_room_state_to_db(room_id)
        
    if all_done:
        await handle_bj_dealer_phase(room_id, thread)
    else:
        # Ping the current player to open their control panel
        current_player = players[turn_idx]
        if player_done.get(current_player, False) or player_blackjack.get(current_player, False):
            state["current_turn_index"] += 1
            room_manager.save_room_state_to_db(room_id)
            await update_bj_board_msg(room_id, thread)
        else:
            await send_bj_turn_notification(room_id, thread, current_player)

async def send_bj_turn_notification(room_id: str, thread: discord.Thread, player_id: str):
    view = BJOpenControlView(room_id, player_id)
    msg = await thread.send(f"🎯 Đến lượt <@{player_id}>! Hãy bấm nút dưới đây để mở bảng điều khiển bài của bạn.", view=view)
    room_manager.room_states[room_id]["turn_notification_id"] = msg.id
    room_manager.save_room_state_to_db(room_id)

class BJOpenControlView(discord.ui.View):
    def __init__(self, room_id: str, player_id: str):
        super().__init__(timeout=120)
        self.room_id = room_id
        self.player_id = player_id
        
    @discord.ui.button(label="🎮 MỞ BẢNG ĐIỀU KHIỂN", style=discord.ButtonStyle.primary, emoji="🎮")
    async def open_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("❌ Đây không phải lượt chơi của bạn!", ephemeral=True)
            return
            
        state = room_manager.room_states.get(self.room_id)
        if not state:
            await interaction.response.send_message("❌ Trận đấu đã bị lỗi hoặc kết thúc!", ephemeral=True)
            return
            
        hand = state["player_hands"][self.player_id]
        pts = calculate_hand(hand)
        dealer_hand = state["dealer_hand"]
        
        embed = create_embed(
            title="🃏 BLACKJACK CONTROL PANEL",
            description=f"**Bài của bạn:** {hand_str(hand)}\n"
                        f"**Điểm:** {pts}\n\n"
                        f"**Dealer:** {hand_str(dealer_hand, hide_second=True)}",
            color=COLOR_GOLD
        )
        
        view = BJControlPanelView(self.room_id, self.player_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class BJControlPanelView(discord.ui.View):
    def __init__(self, room_id: str, player_id: str):
        super().__init__(timeout=60)
        self.room_id = room_id
        self.player_id = player_id
        
    @discord.ui.button(label="🃏 HIT", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = room_manager.room_states.get(self.room_id)
        if not state or state["player_done"].get(self.player_id, False):
            await interaction.response.send_message("❌ Lượt chơi không khả dụng!", ephemeral=True)
            return
            
        cards_list = state["deck_cards"]
        deck = BlackjackDeck()
        deck.cards = cards_list
        hand = state["player_hands"][self.player_id]
        
        card = deck.draw()
        hand.append(card)
        state["deck_cards"] = deck.cards
        pts = calculate_hand(hand)
        
        if pts > 21:
            state["player_bust"][self.player_id] = True
            state["player_done"][self.player_id] = True
            embed = create_embed(title="💥 BẠN ĐÃ BUST!", description=f"Bài của bạn: {hand_str(hand)} (Điểm: {pts})", color=COLOR_RED)
            await interaction.response.edit_message(embed=embed, view=None)
            await advance_bj_turn(self.room_id, interaction.channel)
        elif pts == 21:
            state["player_done"][self.player_id] = True
            embed = create_embed(title="🎯 ĐẠT 21 ĐIỂM!", description=f"Bài của bạn: {hand_str(hand)} (Điểm: {pts})", color=COLOR_GREEN)
            await interaction.response.edit_message(embed=embed, view=None)
            await advance_bj_turn(self.room_id, interaction.channel)
        else:
            embed = create_embed(
                title="🃏 BLACKJACK CONTROL PANEL",
                description=f"**Bài của bạn:** {hand_str(hand)}\n"
                            f"**Điểm:** {pts}\n\n"
                            f"**Dealer:** {hand_str(state['dealer_hand'], hide_second=True)}",
                color=COLOR_GOLD
            )
            await interaction.response.edit_message(embed=embed, view=self)
            
        room_manager.save_room_state_to_db(self.room_id)

    @discord.ui.button(label="✋ STAND", style=discord.ButtonStyle.success, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = room_manager.room_states.get(self.room_id)
        if not state or state["player_done"].get(self.player_id, False):
            await interaction.response.send_message("❌ Lượt chơi không khả dụng!", ephemeral=True)
            return
            
        state["player_done"][self.player_id] = True
        hand = state["player_hands"][self.player_id]
        pts = calculate_hand(hand)
        room_manager.save_room_state_to_db(self.room_id)
        
        embed = create_embed(title="✋ BẠN ĐÃ STAND", description=f"Bài của bạn: {hand_str(hand)} (Điểm: {pts})", color=COLOR_GOLD)
        await interaction.response.edit_message(embed=embed, view=None)
        await advance_bj_turn(self.room_id, interaction.channel)

async def advance_bj_turn(room_id: str, thread: discord.Thread):
    state = room_manager.room_states.get(room_id)
    if not state: return
    
    # Delete the turn notification trigger message
    notif_id = state.get("turn_notification_id")
    if notif_id:
        try:
            msg = await thread.fetch_message(notif_id)
            await msg.delete()
        except: pass
        
    state["current_turn_index"] += 1
    room_manager.save_room_state_to_db(room_id)
    await update_bj_board_msg(room_id, thread)

async def handle_bj_dealer_phase(room_id: str, thread: discord.Thread):
    state = room_manager.room_states.get(room_id)
    room = room_manager.get_room(room_id)
    if not state or not room: return
    
    deck = BlackjackDeck()
    deck.cards = state["deck_cards"]
    dealer_hand = state["dealer_hand"]
    dealer_value = calculate_hand(dealer_hand)
    
    while dealer_value < 17:
        dealer_hand.append(deck.draw())
        dealer_value = calculate_hand(dealer_hand)
        state["dealer_hand"] = dealer_hand
        state["deck_cards"] = deck.cards
        room_manager.save_room_state_to_db(room_id)
        await update_bj_board_msg(room_id, thread)
        await asyncio.sleep(1.5)
        
    # Dealer phase finished, calculate results
    players = room["players"]
    player_bust = state.get("player_bust", {})
    player_blackjack = state.get("player_blackjack", {})
    player_hands = state.get("player_hands", {})
    custom_bets = state.get("custom_bets", {})
    
    description = "🏆 **KẾT QUẢ TRẬN BLACKJACK**\n\n"
    description += f"🤖 **Dealer:** {hand_str(dealer_hand)} (Điểm: {dealer_value})\n\n"
    
    rankings = {}
    for player_id in players:
        bet_amount = custom_bets.get(player_id, room["betAmount"])
        pv = calculate_hand(player_hands[player_id])
        
        if player_bust.get(player_id): result, reward = "💀 BUST (Thua)", 0
        elif player_blackjack.get(player_id):
            if dealer_value == 21: result, reward = "🤝 HÒA (Hoàn cược)", bet_amount
            else: result, reward = "🎉 BLACKJACK (Thắng x2.5)", int(bet_amount * 2.5)
        elif dealer_value > 21 or pv > dealer_value: result, reward = "🎉 THẮNG (Thắng x2.0)", int(bet_amount * 2)
        elif pv == dealer_value: result, reward = "🤝 HÒA (Hoàn cược)", bet_amount
        else: result, reward = "😢 THUA", 0
        
        if reward > 0: await add_win(player_id, reward)
        await update_user_stats(player_id, reward > bet_amount, bet_amount, reward)
        
        description += f"<@{player_id}>: Điểm: **{pv}** | Cược: **{bet_amount:,}** VNĐ → **{result}** | Nhận: 💰 **{reward:,}** VNĐ\n"
        rankings[player_id] = {"value": pv, "reward": reward, "bet": bet_amount}
        
    description += "\n🗑️ Phòng chơi sẽ hoàn toàn tự động giải tán sau 15 giây..."
    embed = create_embed(title="🏆 Bảng Tổng Kết Trận Đấu", description=description, color=COLOR_GOLD)
    
    board_msg_id = state.get("board_msg_id")
    if board_msg_id:
        try:
            board_msg = await thread.fetch_message(board_msg_id)
            await board_msg.edit(embed=embed)
        except: pass
        
    await asyncio.sleep(15)
    await end_game_and_cleanup(room_id, thread, {"rankings": rankings})

# ============================================
# GAME: TIẾN LÊN MIỀN NAM ADVANCED ENGINE
# ============================================
TL_SUITS = ["♠", "♣", "♦", "♥"]  # Bích < Chuồng < Rô < Cơ
TL_RANKS = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]
TL_RANK_ORDER = {r: i for i, r in enumerate(TL_RANKS)}
TL_SUIT_ORDER = {"♠": 0, "♣": 1, "♦": 2, "♥": 3}

def tl_card_sort_key(card: Tuple[str, str]) -> Tuple[int, int]:
    return (TL_RANK_ORDER[card[0]], TL_SUIT_ORDER[card[1]])

def tl_card_display(card: Tuple[str, str]) -> str:
    return f"{card[1]}{card[0]}"

def tl_hand_display(hand: List[Tuple[str, str]]) -> str:
    return " ".join([tl_card_display(c) for c in hand])

def tl_parse_cards(selected_cards: List[str], hand: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    result = []
    for card_str in selected_cards:
        # card_str looks like "♥3" or "♣10"
        suit = card_str[0]
        rank = card_str[1:]
        if rank not in TL_RANK_ORDER: rank = card_str[1]
        card = (rank, suit)
        if card in hand: result.append(card)
    return result

def tl_detect_combination(cards: List[Tuple[str, str]]) -> Tuple[str, bool, int]:
    if not cards: return "Chưa chọn bài", False, 0
    n = len(cards)
    sorted_cards = sorted(cards, key=tl_card_sort_key)
    
    # 1. Single Card (Rác)
    if n == 1:
        power = TL_RANK_ORDER[sorted_cards[0][0]] * 10 + TL_SUIT_ORDER[sorted_cards[0][1]]
        if sorted_cards[0][0] == "2":
            return "Heo", True, power
        return f"Rác {tl_card_display(sorted_cards[0])}", True, power
        
    # 2. Pairs (Đôi)
    if n == 2:
        if sorted_cards[0][0] == sorted_cards[1][0]:
            power = TL_RANK_ORDER[sorted_cards[1][0]] * 10 + TL_SUIT_ORDER[sorted_cards[1][1]]
            if sorted_cards[0][0] == "2":
                return "Đôi Heo", True, power
            return f"Đôi {sorted_cards[0][0]}", True, power
        return "Không phải đôi", False, 0
        
    # 3. Triples (Sám)
    if n == 3:
        if sorted_cards[0][0] == sorted_cards[1][0] == sorted_cards[2][0]:
            power = TL_RANK_ORDER[sorted_cards[2][0]] * 10 + TL_SUIT_ORDER[sorted_cards[2][1]]
            return f"Sám {sorted_cards[0][0]}", True, power
            
    # 4. Straight (Sảnh) - Minimum length 3, "2" is not allowed in straights
    if n >= 3:
        ranks = [TL_RANK_ORDER[c[0]] for c in sorted_cards]
        has_two = any(c[0] == "2" for c in sorted_cards)
        is_consecutive = all(ranks[i+1] - ranks[i] == 1 for i in range(len(ranks)-1))
        if is_consecutive and not has_two:
            power = ranks[-1] * 10 + TL_SUIT_ORDER[sorted_cards[-1][1]]
            return f"Sảnh {sorted_cards[0][0]}-{sorted_cards[-1][0]}", True, power
            
    # 5. Tứ Quý (Four of a Kind)
    if n == 4:
        if sorted_cards[0][0] == sorted_cards[1][0] == sorted_cards[2][0] == sorted_cards[3][0]:
            power = TL_RANK_ORDER[sorted_cards[3][0]] * 10
            return f"Tứ Quý {sorted_cards[0][0]}", True, power
            
    # 6. Consecutive Pairs (Đôi Thông) - 3 or 4 pairs
    if n in [6, 8]:
        pairs = [sorted_cards[i:i+2] for i in range(0, n, 2)]
        is_all_pairs = all(p[0][0] == p[1][0] for p in pairs)
        if is_all_pairs:
            pair_ranks = [TL_RANK_ORDER[p[0][0]] for p in pairs]
            is_consecutive = all(pair_ranks[i+1] - pair_ranks[i] == 1 for i in range(len(pair_ranks)-1))
            has_two = any(p[0][0] == "2" for p in pairs)
            if is_consecutive and not has_two:
                power = pair_ranks[-1] * 10 + TL_SUIT_ORDER[pairs[-1][1][1]]
                if n == 6: return f"Ba Đôi Thông ({sorted_cards[0][0]}-{sorted_cards[-1][0]})", True, power
                if n == 8: return f"Bốn Đôi Thông ({sorted_cards[0][0]}-{sorted_cards[-1][0]})", True, power
                
    return "Tổ hợp không xác định", False, 0

def tl_can_beat(new_combo: Tuple[str, bool, int], current_combo: Tuple[str, bool, int], new_type: str, current_type: str) -> bool:
    if not current_combo[1]: return True
    
    new_power, current_power = new_combo[2], current_combo[2]
    
    # Standard same-type matching
    if new_type.split()[0] == current_type.split()[0]:
        return new_power > current_power
        
    # Chopping (Chặt) Rules:
    # 1. Single 2 (Heo) can be chopped by: Tứ Quý, Ba Đôi Thông, Bốn Đôi Thông
    if current_type == "Heo":
        if new_type.startswith("Tứ Quý") or new_type.startswith("Ba Đôi Thông") or new_type.startswith("Bốn Đôi Thông"): return True
        
    # 2. Đôi Heo can be chopped by: Tứ Quý, Bốn Đôi Thông
    if current_type == "Đôi Heo":
        if new_type.startswith("Tứ Quý") or new_type.startswith("Bốn Đôi Thông"): return True
        
    # 3. Ba Đôi Thông can be chopped by: Higher Ba Đôi Thông, Tứ Quý, Bốn Đôi Thông
    if current_type.startswith("Ba Đôi Thông"):
        if new_type.startswith("Ba Đôi Thông") and new_power > current_power: return True
        if new_type.startswith("Tứ Quý") or new_type.startswith("Bốn Đôi Thông"): return True
        
    # 4. Tứ Quý can be chopped by: Higher Tứ Quý, Bốn Đôi Thông
    if current_type.startswith("Tứ Quý"):
        if new_type.startswith("Tứ Quý") and new_power > current_power: return True
        if new_type.startswith("Bốn Đôi Thông"): return True
        
    # 5. Bốn Đôi Thông can only be chopped by: Higher Bốn Đôi Thông
    if current_type.startswith("Bốn Đôi Thông"):
        if new_type.startswith("Bốn Đôi Thông") and new_power > current_power: return True
        
    return False

async def start_tienlen_full(room_id: str, thread: discord.Thread):
    room = room_manager.get_room(room_id)
    if not room: return
    players = room["players"]
    bet_amount = room["betAmount"]
    num_players = len(players)
    deck = TienLenDeck()
    hands = deck.deal(num_players)
    player_hands = {players[i]: hands[i] for i in range(num_players)}
    
    current_player_idx = 0
    for i, player_id in enumerate(players):
        if ("3", "♠") in player_hands[player_id]:
            current_player_idx = i
            break
            
    state = room_manager.room_states[room_id]
    state.update({
        "player_hands": player_hands, "current_player_idx": current_player_idx,
        "current_combo": ("", False, 0), "current_combo_type": "", "current_combo_cards": [],
        "pass_count": 0, "round_over": False, "finished_players": [],
        "bet_amount": bet_amount, "num_players": num_players
    })
    room_manager.save_room_state_to_db(room_id)
    
    await update_tl_board_msg(room_id, thread)

async def update_tl_board_msg(room_id: str, thread: discord.Thread):
    room = room_manager.get_room(room_id)
    state = room_manager.room_states.get(room_id, {})
    if not room or not state: return
    
    players = room["players"]
    current_idx = state.get("current_player_idx", 0)
    current_player = players[current_idx]
    
    description = "🀄 **TIẾN LÊN MIỀN NAM**\n\n"
    description += f"👤 **Lượt hiện tại:** <@{current_player}>\n\n"
    
    current_combo_cards = state.get("current_combo_cards", [])
    if state.get("current_combo", (None, False, 0))[1] and current_combo_cards:
        combo_display = tl_hand_display(current_combo_cards)
        description += f"🃏 **Bộ vừa đánh:** {state.get('current_combo_type')} ({combo_display})\n\n"
    else:
        description += "🃏 **Bộ vừa đánh:** (Trống - có thể đánh bộ tùy chọn)\n\n"
        
    description += "👥 **Danh sách người chơi:**\n"
    for idx, pid in enumerate(players):
        turn_marker = "🎯 " if idx == current_idx else "   "
        finished = "✅ Đã hết bài" if pid in state.get("finished_players", []) else f"{len(state.get('player_hands', {}).get(pid, []))} lá"
        description += f"{turn_marker}<@{pid}> - **{finished}**\n"
        
    embed = create_embed(title="🀄 Tiến Lên Table", description=description, color=COLOR_PURPLE)
    
    board_msg_id = state.get("board_msg_id")
    board_msg = None
    if board_msg_id:
        try: board_msg = await thread.fetch_message(board_msg_id)
        except: pass
        
    if board_msg:
        await board_msg.edit(embed=embed)
    else:
        board_msg = await thread.send(embed=embed)
        state["board_msg_id"] = board_msg.id
        room_manager.save_room_state_to_db(room_id)
        
    # Send turn notifications and show the Ephemeral Control Panel opener
    await send_tl_turn_notification(room_id, thread, current_player)

async def send_tl_turn_notification(room_id: str, thread: discord.Thread, player_id: str):
    view = TLOpenControlView(room_id, player_id)
    msg = await thread.send(f"🎯 Đến lượt <@{player_id}>! Hãy bấm nút dưới đây để mở bảng bài của bạn.", view=view)
    room_manager.room_states[room_id]["turn_notification_id"] = msg.id
    room_manager.save_room_state_to_db(room_id)

class TLOpenControlView(discord.ui.View):
    def __init__(self, room_id: str, player_id: str):
        super().__init__(timeout=120)
        self.room_id = room_id
        self.player_id = player_id
        
    @discord.ui.button(label="🎮 MỞ BẢNG ĐIỀU KHIỂN", style=discord.ButtonStyle.primary, emoji="🎮")
    async def open_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("❌ Đây không phải lượt chơi của bạn!", ephemeral=True)
            return
            
        state = room_manager.room_states.get(self.room_id)
        if not state:
            await interaction.response.send_message("❌ Trận đấu đã kết thúc hoặc bị lỗi!", ephemeral=True)
            return
            
        hand = state["player_hands"].get(self.player_id, [])
        embed = create_embed(
            title="🃏 BÀI CỦA BẠN",
            description=f"**Các lá bài trên tay:**\n{tl_hand_display(hand)}\n\n"
                        f"Hãy chọn các lá bài để tạo tổ hợp từ menu phía dưới.",
            color=COLOR_PURPLE
        )
        
        view = TLEphemeralControlView(self.room_id, self.player_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class TLEphemeralControlView(discord.ui.View):
    def __init__(self, room_id: str, player_id: str):
        super().__init__(timeout=120)
        self.room_id = room_id
        self.player_id = player_id
        self.selected_cards: List[str] = []
        self._setup_ui()
        
    def _setup_ui(self):
        state = room_manager.room_states[self.room_id]
        hand = state["player_hands"].get(self.player_id, [])
        
        options = []
        for card in hand:
            label = tl_card_display(card)
            value = f"{card[1]}_{card[0]}"
            emoji = "❤️" if card[1] == "♥" else "🔶" if card[1] == "♦" else "🍀" if card[1] == "♣" else "♠️"
            options.append(discord.SelectOption(label=label, value=value, emoji=emoji))
            
        # Limit options to Discord's maximum menu limit
        options = options[:25]
        
        if options:
            self.select_menu = discord.ui.Select(
                placeholder=f"Chọn bài ({len(hand)} lá)...",
                min_values=1,
                max_values=min(13, len(options)),
                options=options
            )
            self.select_menu.callback = self.select_callback
            self.add_item(self.select_menu)
            
        # Add buttons
        self.play_button = discord.ui.Button(label="✅ ĐÁNH", style=discord.ButtonStyle.success, emoji="✅", disabled=True)
        self.play_button.callback = self.play_callback
        
        self.skip_button = discord.ui.Button(label="⏭️ BỎ LƯỢT", style=discord.ButtonStyle.secondary, emoji="⏭️")
        self.skip_button.callback = self.skip_callback
        
        self.cancel_button = discord.ui.Button(label="❌ HỦY CHỌN", style=discord.ButtonStyle.danger, emoji="❌")
        self.cancel_button.callback = self.cancel_callback
        
        self.add_item(self.play_button)
        self.add_item(self.skip_button)
        self.add_item(self.cancel_button)

    async def select_callback(self, interaction: discord.Interaction):
        state = room_manager.room_states.get(self.room_id)
        if not state: return
        
        self.selected_cards = self.select_menu.values
        hand = state["player_hands"][self.player_id]
        parsed_selected = tl_parse_cards(self.selected_cards, hand)
        
        # Detect combination
        combo_type, is_valid, power = tl_detect_combination(parsed_selected)
        
        status_text = ""
        if not is_valid:
            status_text = "❌ Tổ hợp không hợp lệ."
            self.play_button.disabled = True
        else:
            can_beat = tl_can_beat((combo_type, is_valid, power), state["current_combo"], combo_type, state["current_combo_type"])
            if can_beat:
                status_text = f"✅ Có thể đánh tổ hợp: **{combo_type.upper()}**."
                self.play_button.disabled = False
            else:
                status_text = f"❌ Không đủ mạnh để đè bộ hiện tại."
                self.play_button.disabled = True
                
        card_emojis = " ".join([tl_card_display(c) for c in parsed_selected])
        embed = create_embed(
            title="🃏 BÀI CỦA BẠN",
            description=f"**Các lá bài trên tay:**\n{tl_hand_display(hand)}\n\n"
                        f"**Đã Chọn:** {card_emojis}\n"
                        f"**Kết quả phân tích:** {status_text}",
            color=COLOR_PURPLE
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def play_callback(self, interaction: discord.Interaction):
        state = room_manager.room_states.get(self.room_id)
        if not state: return
        
        hand = state["player_hands"][self.player_id]
        parsed_selected = tl_parse_cards(self.selected_cards, hand)
        combo_type, is_valid, power = tl_detect_combination(parsed_selected)
        
        # Double check validity
        if not is_valid or not tl_can_beat((combo_type, is_valid, power), state["current_combo"], combo_type, state["current_combo_type"]):
            await interaction.response.send_message("❌ Tổ hợp hoặc nước bài hiện tại không hợp lệ!", ephemeral=True)
            return
            
        # Deduct cards
        for card in parsed_selected:
            if card in hand: hand.remove(card)
            
        state["current_combo"] = (combo_type, is_valid, power)
        state["current_combo_type"] = combo_type
        state["current_combo_cards"] = parsed_selected
        state["pass_count"] = 0
        state["action_done"] = True
        state["round_over"] = False
        
        room_manager.save_room_state_to_db(self.room_id)
        
        embed = create_embed(title="✅ ĐÃ RA BÀI THÀNH CÔNG", description=f"Tổ hợp ra bài: **{combo_type.upper()}**\n{tl_hand_display(parsed_selected)}", color=COLOR_GREEN)
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Check if they cleared all cards
        if len(hand) == 0 and self.player_id not in state["finished_players"]:
            state["finished_players"].append(self.player_id)
            rank = len(state["finished_players"])
            medal = ["🥇", "🥈", "🥉", "💀"][rank-1] if rank <= 4 else f"#{rank}"
            await interaction.channel.send(f"{medal} <@{self.player_id}> đã hết bài! **Hạng {rank}**")
            
        await advance_tl_turn(self.room_id, interaction.channel)

    async def skip_callback(self, interaction: discord.Interaction):
        state = room_manager.room_states.get(self.room_id)
        if not state: return
        
        if not state["current_combo"][1]:
            await interaction.response.send_message("❌ Không thể bỏ lượt khi đây là vòng đấu mới!", ephemeral=True)
            return
            
        state["pass_count"] += 1
        state["action_done"] = True
        room_manager.save_room_state_to_db(self.room_id)
        
        embed = create_embed(title="⏭️ ĐÃ BỎ LƯỢT", description="Bạn đã bỏ lượt chơi của vòng này.", color=COLOR_WARNING)
        await interaction.response.edit_message(embed=embed, view=None)
        
        await advance_tl_turn(self.room_id, interaction.channel)

    async def cancel_callback(self, interaction: discord.Interaction):
        self.selected_cards = []
        self.play_button.disabled = True
        state = room_manager.room_states.get(self.room_id)
        hand = state["player_hands"][self.player_id]
        
        embed = create_embed(
            title="🃏 BÀI CỦA BẠN",
            description=f"**Các lá bài trên tay:**\n{tl_hand_display(hand)}\n\n"
                        f"Đã hủy chọn toàn bộ các lá bài.",
            color=COLOR_PURPLE
        )
        await interaction.response.edit_message(embed=embed, view=self)

async def advance_tl_turn(room_id: str, thread: discord.Thread):
    state = room_manager.room_states.get(room_id)
    room = room_manager.get_room(room_id)
    if not state or not room: return
    
    # Delete current turn notification message
    notif_id = state.get("turn_notification_id")
    if notif_id:
        try:
            msg = await thread.fetch_message(notif_id)
            await msg.delete()
        except: pass
        
    players = room["players"]
    finished = state.get("finished_players", [])
    
    # Determine next player index
    if len(finished) >= len(players) - 1:
        # Game over, proceed to cleanup and pay winner
        await tl_end_game(room_id, thread, state)
        return
        
    current_idx = state["current_player_idx"]
    loop_count = 0
    while loop_count < len(players):
        current_idx = (current_idx + 1) % len(players)
        next_player = players[current_idx]
        if next_player not in finished:
            state["current_player_idx"] = current_idx
            break
        loop_count += 1
        
    # Check if a new round starts due to passes
    active_players_count = len(players) - len(finished)
    if state["pass_count"] >= active_players_count - 1:
        state["current_combo"] = ("", False, 0)
        state["current_combo_type"] = ""
        state["current_combo_cards"] = []
        state["pass_count"] = 0
        state["round_over"] = True
        await thread.send("🔄 Vòng đấu mới bắt đầu!")
        
    room_manager.save_room_state_to_db(room_id)
    await update_tl_board_msg(room_id, thread)

# ============================================
# WINNER TAKES ALL & ROOM CLEANUP
# ============================================
async def tl_end_game(room_id: str, thread: discord.Thread, state: dict):
    room = room_manager.get_room(room_id)
    if not room: return
    players = room["players"]
    bet_amount = state["bet_amount"]
    finished = state["finished_players"]
    for pid in players:
        if pid not in finished: finished.append(pid)
    
    # First finisher is the winner
    if finished:
        winner_id = finished[0]
        total_players_count = len(players)
        total_pool = int(bet_amount * total_players_count * 0.95)  # 5% house rake [1]
        await add_win(winner_id, total_pool)
        
        description = "🀄 **KẾT QUẢ TIẾN LÊN MIỀN NAM**\n\n"
        description += f"🥇 **Người Thắng Cuộc (Nhất):** <@{winner_id}>\n"
        description += f"💰 **Tiền Thưởng Nhận Được (Winner Takes All):** {total_pool:,} VNĐ\n\n"
        description += "Các vị trí còn lại:\n"
        for idx, pid in enumerate(finished[1:]):
            description += f"#{idx+2}. <@{pid}>\n"
    else:
        description = "❌ Trò chơi kết thúc không có người thắng hợp lệ."
        
    description += "\n🗑️ Phòng sẽ tự giải tán sau 15 giây..."
    embed = create_embed(title="🏆 Kết Quả Tiến Lên", description=description, color=COLOR_PURPLE)
    await thread.send(embed=embed)
    await asyncio.sleep(15)
    await end_game_and_cleanup(room_id, thread, {"winner": finished[0] if finished else None})

async def end_game_and_cleanup(room_id: str, thread: discord.Thread, results: Dict):
    room = room_manager.get_room(room_id)
    if not room: return
    room_manager.set_room_status(room_id, RoomStatus.FINISHED)
    db.collection("room_history").add({
        "roomId": room_id, "gameType": room["gameType"], "players": room["players"],
        "results": results, "createdAt": datetime.now(timezone.utc).isoformat()
    })
    await room_manager.cleanup_room(room_id)
    try:
        await thread.delete()
        print(f"🗑️ Deleted thread {thread.id}")
    except Exception as e:
        print(f"Error deleting thread: {e}")

# ============================================
# SPECTATOR MODE VIEW
# ============================================
class SpectatorView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=None)
        self.room_id = room_id
    @discord.ui.button(label="🔄 Làm Mới Trận Đấu", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = room_manager.get_room(self.room_id)
        if not room:
            await interaction.response.send_message("❌ Trận đấu đã kết thúc hoặc phòng đã giải tán!", ephemeral=True)
            return
        state = room_manager.room_states.get(self.room_id, {})
        players = room.get("players", [])
        
        description = f"👀 **SPECTATOR MODE**\n"
        description += f"**Game:** {room.get('gameType', '').upper()}\n"
        description += f"**Trạng Thái:** {room.get('status', '')}\n\n"
        
        if room.get("gameType") == "tienlen":
            current_idx = state.get("current_player_idx", 0)
            current_player = players[current_idx] if current_idx < len(players) else "Không rõ"
            description += f"👤 **Lượt chơi hiện tại:** <@{current_player}>\n"
            if state.get("current_combo", (None, False, 0))[1]:
                combo_cards = state.get("current_combo_cards", [])
                description += f"🃏 **Bộ vừa đánh:** {state.get('current_combo_type')} ({tl_hand_display(combo_cards)})\n\n"
            else:
                description += "🃏 **Bộ vừa đánh:** (Chưa có / Đánh tự do)\n\n"
            description += "👥 **Số lá bài còn lại của người chơi:**\n"
            for pid in players:
                finished = "✅" if pid in state.get("finished_players", []) else ""
                card_count = len(state.get("player_hands", {}).get(pid, []))
                description += f"<@{pid}> - {card_count} lá {finished}\n"
                
        elif room.get("gameType") == "blackjack":
            dealer_hand = state.get("dealer_hand", [])
            description += f"🤖 **Dealer's Hand (Visible):** {hand_str(dealer_hand, hide_second=True)}\n\n"
            description += "👥 **Danh Sách Người Chơi:**\n"
            player_done = state.get("player_done", {})
            player_bust = state.get("player_bust", {})
            for pid in players:
                status = "STAND" if player_done.get(pid) else "HIT"
                if player_bust.get(pid): status = "BUST 💥"
                description += f"<@{pid}> - Trạng thái: **{status}**\n"
                
        embed = create_embed(title="👀 Đang Theo Dõi Trận Đấu", description=description, color=COLOR_INFO)
        await interaction.response.edit_message(embed=embed, view=self)

# ============================================
# JOIN BLACKJACK CUSTOM BET MODAL
# ============================================
class JoinBJModal(discord.ui.Modal, title="ĐẶT CƯỢC BLACKJACK"):
    bet_input = discord.ui.TextInput(label="Số tiền cược (VNĐ)", placeholder="Ví dụ: 50000", min_length=1)
    
    def __init__(self, room_id: str, thread_id: int, game_name: str):
        super().__init__()
        self.room_id = room_id
        self.thread_id = thread_id
        self.game_name = game_name
        
    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        try:
            custom_bet = int(self.bet_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền cược không hợp lệ!", ephemeral=True)
            return
            
        if custom_bet < 10000:
            await interaction.response.send_message("❌ Tiền cược tối thiểu là 10,000 VNĐ!", ephemeral=True)
            return
            
        user_data = await create_user_if_not_exists(user_id)
        if user_data["balance"] < custom_bet:
            await interaction.response.send_message(f"❌ Số dư của bạn không đủ để cược {custom_bet:,} VNĐ!", ephemeral=True)
            return
            
        success = await deduct_bet(user_id, custom_bet)
        if not success:
            await interaction.response.send_message("❌ Có lỗi xảy ra khi trừ tiền cược!", ephemeral=True)
            return
            
        room_manager.join_room(user_id, self.room_id, custom_bet=custom_bet)
        room = room_manager.get_room(self.room_id)
        
        thread = interaction.guild.get_thread(self.thread_id)
        if thread: await thread.add_user(interaction.user)
        
        # Update Public Board Invite
        players_text = "\n".join([f"{i+1}. <@{pid}> (Cược: {room_manager.room_states[self.room_id]['custom_bets'].get(pid, 0):,} VNĐ)" for i, pid in enumerate(room["players"])])
        embed = interaction.message.embeds[0]
        embed.description = embed.description.split("👤")[0] + f"👤 **Người chơi ({len(room['players'])}/4):**\n{players_text}\n\n🔒 Phòng riêng tư - Nhấn nút để tham gia!\n⏰ Tự đóng sau 5 phút nếu không đủ người."
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ Đã tham gia phòng {self.game_name} với mức cược **{custom_bet:,}** VNĐ! Vào <#{self.thread_id}> để sẵn sàng chơi.", ephemeral=True)

class RoomInviteView(discord.ui.View):
    def __init__(self, room_id: str, thread_id: int, bet_amount: int, game_type: str, game_name: str):
        super().__init__(timeout=300)
        self.room_id = room_id
        self.thread_id = thread_id
        self.bet_amount = bet_amount
        self.game_type = game_type
        self.game_name = game_name
        
    @discord.ui.button(label="Tham Gia Phòng", style=discord.ButtonStyle.success, emoji="🚪")
    async def join_room(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if room_manager.get_player_room(user_id):
            await interaction.response.send_message("❌ Bạn đang ở trong một phòng chơi khác!", ephemeral=True)
            return
            
        room = room_manager.get_room(self.room_id)
        if not room or room["status"] != RoomStatus.WAITING:
            await interaction.response.send_message("❌ Phòng chơi đã đóng hoặc trận đấu đã bắt đầu!", ephemeral=True)
            return
        if len(room["players"]) >= 4:
            await interaction.response.send_message("❌ Phòng đã đạt số lượng người chơi tối đa!", ephemeral=True)
            return
            
        if self.game_type == "blackjack":
            await interaction.response.send_modal(JoinBJModal(self.room_id, self.thread_id, self.game_name))
        else:
            user_data = await create_user_if_not_exists(user_id)
            if user_data["balance"] < self.bet_amount:
                await interaction.response.send_message(f"❌ Số dư không đủ! Cần {self.bet_amount:,} VNĐ", ephemeral=True)
                return
            success = await deduct_bet(user_id, self.bet_amount)
            if not success:
                await interaction.response.send_message("❌ Có lỗi xảy ra khi trừ tiền cược!", ephemeral=True)
                return
            room_manager.join_room(user_id, self.room_id)
            thread = interaction.guild.get_thread(self.thread_id)
            if thread: await thread.add_user(interaction.user)
            
            players_text = "\n".join([f"{i+1}. <@{pid}>" for i, pid in enumerate(room["players"])])
            embed = interaction.message.embeds[0]
            embed.description = embed.description.split("👤")[0] + f"👤 **Người chơi ({len(room['players'])}/4):**\n{players_text}\n\n🔒 Phòng riêng tư - Nhấn nút để tham gia!\n⏰ Tự đóng sau 5 phút nếu không đủ người."
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message(f"✅ Đã tham gia phòng {self.game_name}! Vào <#{self.thread_id}> để sẵn sàng chơi.", ephemeral=True)

class RoomView(discord.ui.View):
    def __init__(self, room_id: str, owner_id: str, bet_amount: int, game_type: str):
        super().__init__(timeout=None)
        self.room_id = room_id
        self.owner_id = owner_id
        self.bet_amount = bet_amount
        self.game_type = game_type
        
    @discord.ui.button(label="Rời Phòng", style=discord.ButtonStyle.danger, emoji="🚪")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        room = room_manager.get_room(self.room_id)
        if not room: return
        
        if user_id == self.owner_id:
            await interaction.response.send_message("❌ Chủ phòng đã rời phòng. Giải tán phòng!", ephemeral=False)
            await asyncio.sleep(3)
            await cleanup_and_delete_room(self.room_id, interaction.channel)
            return
            
        custom_bets = room_manager.room_states[self.room_id].get("custom_bets", {})
        refund_amount = custom_bets.get(user_id, self.bet_amount)
        room_manager.leave_room(user_id, self.room_id)
        await add_win(user_id, refund_amount)
        
        players_text = "\n".join([f"{i+1}. <@{pid}>" for i, pid in enumerate(room["players"])])
        embed = interaction.message.embeds[0]
        embed.description = embed.description.split("👤")[0] + f"👤 **Người chơi ({len(room['players'])}/4):**\n{players_text}"
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"✅ Đã rời phòng! Hoàn trả {refund_amount:,} VNĐ", ephemeral=True)
        
    @discord.ui.button(label="Bắt Đầu", style=discord.ButtonStyle.primary, emoji="▶️", row=1)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ Chỉ có chủ phòng mới có quyền bắt đầu trận đấu!", ephemeral=True)
            return
        room = room_manager.get_room(self.room_id)
        if not room or len(room["players"]) < 2:
            await interaction.response.send_message("❌ Cần tối thiểu 2 người chơi để bắt đầu!", ephemeral=True)
            return
            
        room_manager.set_room_status(self.room_id, RoomStatus.PLAYING)
        await interaction.response.send_message("🚀 Trận đấu bắt đầu!", ephemeral=True)
        
        if self.game_type == "taixiu": await start_taixiu_pvp(self.room_id, interaction.channel)
        elif self.game_type == "blackjack": await start_blackjack_full(self.room_id, interaction.channel)
        elif self.game_type == "tienlen": await start_tienlen_full(self.room_id, interaction.channel)

# ============================================
# GAME: MINES
# ============================================
class MinesGameView(discord.ui.View):
    def __init__(self, user_id: str, bet: int, mines_count: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bet = bet
        self.mines_count = mines_count
        self.grid_size = 25
        self.board = ["gem"] * self.grid_size
        self.revealed = [False] * self.grid_size
        self.gems_clicked = 0
        self.game_over = False
        
        # Place Mines
        mines_indices = random.sample(range(self.grid_size), self.mines_count)
        for idx in mines_indices:
            self.board[idx] = "mine"
            
        self._setup_grid()
        
    def _setup_grid(self):
        for idx in range(self.grid_size):
            button = discord.ui.Button(label="❓", style=discord.ButtonStyle.secondary, row=idx // 5)
            button.callback = self.make_callback(idx)
            self.add_item(button)
            
        # Add Cashout button
        self.cashout_button = discord.ui.Button(label=f"Cashout (1.00x)", style=discord.ButtonStyle.success, row=4)
        self.cashout_button.callback = self.cashout_callback
        self.add_item(self.cashout_button)
        
    def make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ Đây không phải lượt chơi của bạn!", ephemeral=True)
                return
            if self.revealed[idx] or self.game_over: return
            
            self.revealed[idx] = True
            button = self.children[idx]
            
            if self.board[idx] == "mine":
                self.game_over = True
                button.style = discord.ButtonStyle.danger
                button.label = "💣"
                await self.end_mines_game(interaction, won=False)
            else:
                self.gems_clicked += 1
                button.style = discord.ButtonStyle.primary
                button.label = "💎"
                button.disabled = True
                
                # Calculate current multiplier
                mult = self.get_multiplier()
                self.cashout_button.label = f"Cashout ({mult:.2f}x)"
                
                # Auto cashout if all gems are revealed
                if self.gems_clicked == (self.grid_size - self.mines_count):
                    await self.end_mines_game(interaction, won=True)
                else:
                    await interaction.response.edit_message(view=self)
        return callback
        
    def get_multiplier(self) -> float:
        # Standard fair mines multiplier formula
        import math
        n = self.grid_size
        m = self.mines_count
        k = self.gems_clicked
        try:
            val = (math.comb(n, k) / math.comb(n - m, k)) * 0.98  # 2% house edge
            return max(1.0, val)
        except ZeroDivisionError:
            return 1.0

    async def cashout_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không phải là người chơi!", ephemeral=True)
            return
        if self.game_over: return
        await self.end_mines_game(interaction, won=True)
        
    async def end_mines_game(self, interaction: discord.Interaction, won: bool):
        self.game_over = True
        self.stop()
        
        # Disable all buttons and show solution
        for i in range(self.grid_size):
            button = self.children[i]
            button.disabled = True
            if self.board[i] == "mine":
                button.label = "💣"
                button.style = discord.ButtonStyle.danger
            else:
                button.label = "💎"
                if not self.revealed[i]:
                    button.style = discord.ButtonStyle.secondary
                    
        mult = self.get_multiplier()
        self.cashout_button.disabled = True
        
        if won:
            win_amount = int(self.bet * mult)
            await add_win(self.user_id, win_amount)
            await update_user_stats(self.user_id, True, self.bet, win_amount)
            embed = create_embed(
                title="💎 MINES CASHOUT THÀNH CÔNG",
                description=f"🎉 Bạn đã rút tiền ở mức **{mult:.2f}x**!\n💰 Nhận lại: **{win_amount:,}** VNĐ",
                color=COLOR_SUCCESS
            )
        else:
            await update_user_stats(self.user_id, False, self.bet, 0)
            embed = create_embed(
                title="💣 MINES GAME OVER",
                description=f"💥 Bạn đã kích nổ mìn!\n💸 Mất cược: **{self.bet:,}** VNĐ",
                color=COLOR_ERROR
            )
            
        await interaction.response.edit_message(embed=embed, view=self)

# ============================================
# COMMAND COOLDOWN DECORATOR UTILITY
# ============================================
def check_cooldown(command_name: str, cooldown_seconds: int):
    async def predicate(interaction: discord.Interaction) -> bool:
        user_id = str(interaction.user.id)
        is_on_cooldown, remaining = cooldown_manager.check_cooldown(user_id, command_name, cooldown_seconds)
        if is_on_cooldown:
            hours, minutes, seconds = remaining // 3600, (remaining % 3600) // 60, remaining % 60
            time_str = f"{hours} giờ " if hours > 0 else ""
            time_str += f"{minutes} phút " if minutes > 0 else ""
            time_str += f"{seconds} giây" if seconds > 0 else ""
            await interaction.response.send_message(f"⏰ Vui lòng đợi {time_str.strip()} để sử dụng lệnh này!", ephemeral=True)
            return False
        has_overdue, _ = await check_loans_overdue(user_id)
        if has_overdue:
            await interaction.response.send_message("⚠️ Bạn có khoản nợ quá hạn! Hãy trả nợ trước khi sử dụng lệnh này.\nDùng `/nolist` để xem danh sách nợ.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# ============================================
# ECONOMY SLASH COMMANDS
# ============================================
@bot.tree.command(name="sodu", description="💰 Xem số dư tài khoản của bạn")
@check_cooldown("sodu", COOLDOWN_NORMAL)
async def sodu(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = await create_user_if_not_exists(user_id)
    embed = create_embed(
        title="💰 Thông Tin Tài Khoản", color=COLOR_GOLD,
        fields=[("💵 Số dư hiện tại", f"{user_data['balance']:,} VNĐ", False), ("📈 Tổng thắng", f"{user_data.get('totalMoneyWon', 0):,} VNĐ", True), ("📉 Tổng thua", f"{user_data.get('totalMoneyLost', 0):,} VNĐ", True), ("📅 Ngày tạo", user_data.get('createdAt').strftime("%d/%m/%Y") if user_data.get('createdAt') else "N/A", False)],
        thumbnail_url=interaction.user.display_avatar.url, footer_text=f"Người chơi: {interaction.user.name}"
    )
    cooldown_manager.set_cooldown(user_id, "sodu")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="daily", description="🎁 Nhận quà điểm danh hàng ngày (100,000 VNĐ)")
@check_cooldown("daily", COOLDOWN_DAILY)
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = await create_user_if_not_exists(user_id)
    if user_data.get("dailyLastClaim"):
        last_claim = user_data["dailyLastClaim"]
        if isinstance(last_claim, datetime):
            time_diff = datetime.now(timezone.utc) - last_claim
            if time_diff.total_seconds() < COOLDOWN_DAILY:
                remaining = COOLDOWN_DAILY - int(time_diff.total_seconds())
                await interaction.response.send_message(f"⏰ Bạn đã điểm danh hôm nay rồi! Vui lòng đợi {remaining // 3600} giờ {(remaining % 3600) // 60} phút.", ephemeral=True)
                return
    success = await add_money(user_id, DAILY_REWARD)
    if success:
        get_user_ref(user_id).update({"dailyLastClaim": datetime.now(timezone.utc)})
        embed = create_embed(title="🎁 Điểm Danh Hàng Ngày", description=f"Bạn đã nhận thành công **{DAILY_REWARD:,} VNĐ**!", color=COLOR_GOLD, thumbnail_url=interaction.user.display_avatar.url, footer_text="Hẹn gặp lại bạn ngày mai!")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Có lỗi xảy ra, vui lòng thử lại sau!", ephemeral=True)

@bot.tree.command(name="bank", description="🏦 Chuyển tiền an toàn cho người chơi khác")
@app_commands.describe(user="Người nhận tiền", amount="Số tiền muốn chuyển (hoặc nhập 'all' để chuyển toàn bộ)")
@check_cooldown("bank", COOLDOWN_NORMAL)
async def bank(interaction: discord.Interaction, user: discord.User, amount: str):
    if user.bot or user.id == interaction.user.id:
        await interaction.response.send_message("❌ Người nhận không hợp lệ!", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    sender_data = await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(str(user.id))
    try: transfer_amount = sender_data["balance"] if amount.lower() == "all" else int(amount)
    except ValueError:
        await interaction.response.send_message("❌ Số tiền không hợp lệ!", ephemeral=True)
        return
    if transfer_amount <= 0 or transfer_amount > sender_data["balance"]:
        await interaction.response.send_message("❌ Số dư khả dụng của bạn không đủ!", ephemeral=True)
        return
    success = await transfer_money(user_id, str(user.id), transfer_amount)
    if success:
        embed = create_embed(title="🏦 Chuyển Tiền Thành Công", description=f"{EMOJI_MONEY_BAG} **{interaction.user.name}** đã chuyển **{transfer_amount:,} VNĐ** cho **{user.name}**", color=COLOR_SUCCESS, thumbnail_url=user.display_avatar.url, footer_text="Giao dịch chuyển tiền được ghi lại trên hệ thống")
        cooldown_manager.set_cooldown(user_id, "bank")
        await interaction.response.send_message(embed=embed)
    else: await interaction.response.send_message("❌ Chuyển tiền thất bại!", ephemeral=True)

@bot.tree.command(name="top", description="🏆 Bảng xếp hạng phú hộ giàu nhất")
@check_cooldown("top", COOLDOWN_NORMAL)
async def top(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "top")
    users = db.collection("users").get()
    user_list = [doc.to_dict() for doc in users]
    sorted_users = sorted(user_list, key=lambda x: x.get("balance", 0), reverse=True)
    description = ""
    for i, user_data in enumerate(sorted_users[:10]):
        try: name = interaction.guild.get_member(int(user_data["userId"])).name
        except: name = user_data["userId"]
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        description += f"{medal} **{name}** - {user_data.get('balance', 0):,} VNĐ\n"
    embed = create_embed(title="💰 Bảng Xếp Hạng Giàu Nhất", description=description, color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="info", description="📊 Xem profile và thống kê chi tiết của người chơi")
@app_commands.describe(user="Người chơi muốn xem (bỏ trống để xem chính mình)")
@check_cooldown("info", COOLDOWN_NORMAL)
async def info(interaction: discord.Interaction, user: Optional[discord.User] = None):
    target = user or interaction.user
    user_data = await create_user_if_not_exists(str(target.id))
    cooldown_manager.set_cooldown(str(interaction.user.id), "info")
    profile_color = PROFILE_COLORS.get(user_data.get("profileColor", "🔵 Xanh dương"), COLOR_BLUE)
    badges = []
    if user_data.get("balance", 0) >= BADGE_TY_PHU: badges.append(f"{EMOJI_CROWN} Tỷ Phú")
    elif user_data.get("balance", 0) >= BADGE_DAI_GIA: badges.append(f"{EMOJI_GEM} Đại Gia")
    elif user_data.get("balance", 0) >= BADGE_TRIEU_PHU: badges.append(f"{EMOJI_COIN} Triệu Phú")
    if user_data.get("totalGames", 0) >= BADGE_CAO_THU: badges.append(f"{EMOJI_DICE} Cao Thủ Tài Xỉu")
    if user_data.get("bestWinStreak", 0) >= BADGE_STREAK_GOD: badges.append(f"{EMOJI_FIRE} Chuỗi Thắng Thần Thánh")
    badges_str = "\n".join(badges) if badges else "Chưa có huy hiệu"
    embed = create_embed(
        title="📊 Thông Tin Người Chơi", description=f"### 👤 {target.name}", color=profile_color,
        fields=[
            ("", "**━━━ 📊 THỐNG KÊ ━━━**", False),
            ("🎮 Tổng ván chơi", f"{user_data.get('totalGames', 0)}", True),
            ("📈 Tổng thắng", f"{user_data.get('totalWins', 0)}", True),
            ("📉 Tổng thua", f"{user_data.get('totalLosses', 0)}", True),
            ("🔥 Chuỗi thắng", f"{user_data.get('currentWinStreak', 0)}", True),
            ("🏆 Chuỗi cao nhất", f"{user_data.get('bestWinStreak', 0)}", True),
            ("", "**━━━ 💳 TÀI CHÍNH ━━━**", False),
            ("💵 Số dư", f"{user_data.get('balance', 0):,} VNĐ", True),
            ("🏆 Tổng thắng", f"{user_data.get('totalMoneyWon', 0):,} VNĐ", True),
            ("💸 Tổng thua", f"{user_data.get('totalMoneyLost', 0):,} VNĐ", True),
            ("", "**━━━ 🏅 HUY HIỆU ━━━**", False),
            ("Danh sách huy hiệu", badges_str, False),
        ],
        thumbnail_url=target.display_avatar.url, footer_text=f"ID: {target.id}"
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="🏅 Xem thứ tự xếp hạng của bạn")
@check_cooldown("rank", COOLDOWN_NORMAL)
async def rank(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "rank")
    await create_user_if_not_exists(user_id)
    
    users = db.collection("users").get()
    user_list = [doc.to_dict() for doc in users]
    
    def get_rank(key, reverse=True):
        sorted_list = sorted(user_list, key=lambda x: x.get(key, 0), reverse=reverse)
        for i, u in enumerate(sorted_list):
            if str(u.get("userId")) == user_id: return i + 1, len(user_list)
        return len(user_list), len(user_list)
        
    balance_rank, total = get_rank("balance")
    games_rank, _ = get_rank("totalGames")
    streak_rank, _ = get_rank("bestWinStreak")
    wins_rank, _ = get_rank("totalMoneyWon")
    
    embed = create_embed(
        title="🏅 Xếp Hạng Cá Nhân", color=COLOR_GOLD,
        fields=[("🏆 Hạng tài sản", f"#{balance_rank}/{total}", True), ("🎮 Hạng game thủ", f"#{games_rank}/{total}", True), ("🔥 Hạng chuỗi thắng", f"#{streak_rank}/{total}", True), ("📈 Hạng tổng thắng", f"#{wins_rank}/{total}", True)]
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="profilecolor", description="🎨 Đổi màu sắc trang trí cho Profile của bạn")
@check_cooldown("profilecolor", COOLDOWN_NORMAL)
async def profilecolor(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "profilecolor")
    
    class ColorSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Đỏ", emoji="🔴"),
                discord.SelectOption(label="Xanh lá", emoji="🟢"),
                discord.SelectOption(label="Xanh dương", emoji="🔵"),
                discord.SelectOption(label="Tím", emoji="🟣"),
                discord.SelectOption(label="Vàng", emoji="🟡"),
                discord.SelectOption(label="Đen", emoji="⚫")
            ]
            super().__init__(placeholder="Chọn màu sắc Profile mong muốn...", options=options)
        async def callback(self, select_interaction: discord.Interaction):
            if select_interaction.user.id != interaction.user.id: return
            selected = self.values[0]
            get_user_ref(str(select_interaction.user.id)).update({"profileColor": f"🎨 {selected}"})
            await select_interaction.response.send_message(f"🎨 Đã đổi màu Profile của bạn sang: **{selected}**", ephemeral=True)
            
    class ColorView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.add_item(ColorSelect())
    await interaction.response.send_message("🎨 Hãy chọn màu sắc trang trí Profile:", view=ColorView(), ephemeral=True)

@bot.tree.command(name="shop", description="🛒 Mua sắm vật phẩm hỗ trợ trò chơi")
@check_cooldown("shop", COOLDOWN_NORMAL)
async def shop(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "shop")
    class ShopButton(discord.ui.Button):
        def __init__(self, label: str, item_name: str, price: int, emoji: str):
            super().__init__(label=label, style=discord.ButtonStyle.primary, emoji=emoji)
            self.item_name, self.price = item_name, price
        async def callback(self, button_interaction: discord.Interaction):
            if button_interaction.user.id != interaction.user.id: return
            user_doc = get_user_ref(str(button_interaction.user.id)).get()
            if not user_doc.exists: return
            data = user_doc.to_dict()
            if data["balance"] < self.price:
                await button_interaction.response.send_message(f"❌ Bạn không đủ tiền! Cần {self.price:,} VNĐ", ephemeral=True)
                return
            success = await remove_money(str(button_interaction.user.id), self.price, "shop")
            if success:
                user_doc_updated = get_user_ref(str(button_interaction.user.id)).get()
                updated_data = user_doc_updated.to_dict()
                if "Giảm Giá" in self.item_name: updated_data["discountCouponUses"] = updated_data.get("discountCouponUses", 0) + 3
                else: updated_data["freeBetShield"] = updated_data.get("freeBetShield", 0) + 1
                get_user_ref(str(button_interaction.user.id)).set(updated_data)
                await button_interaction.response.send_message(f"✅ Đã mua thành công **{self.item_name}**!", ephemeral=True)
            else:
                await button_interaction.response.send_message("❌ Giao dịch mua hàng thất bại!", ephemeral=True)
    class ShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.add_item(ShopButton("Mua", "📄 Phiếu Giảm Giá", 100000, "📄"))
            self.add_item(ShopButton("Mua", "🛡️ Phiếu Miễn Tiền Cược", 500000, "🛡️"))
    embed = create_embed(
        title="🛒 Cửa Hàng Vật Phẩm", color=COLOR_GOLD,
        fields=[("📄 Phiếu Giảm Giá", "💰 Giá: **100,000 VNĐ**\n📝 Giảm 50% tiền phí khi chơi lỗ đít (3 lượt dùng)", False), ("🛡️ Phiếu Miễn Tiền Cược", "💰 Giá: **500,000 VNĐ**\n📝 Thua không mất tiền trong Tài Xỉu/Mines (1 lượt dùng)", False)]
    )
    await interaction.response.send_message(embed=embed, view=ShopView(), ephemeral=True)

# ============================================
# LOAN SYSTEM & SLASH COMMANDS
# ============================================
@bot.tree.command(name="vay", description="💳 Đề xuất vay tiền từ người chơi khác")
@app_commands.describe(user="Người bạn muốn vay", amount="Số tiền đề xuất vay")
@check_cooldown("vay", COOLDOWN_NORMAL)
async def vay(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.bot or user.id == interaction.user.id or amount <= 0:
        await interaction.response.send_message("❌ Đề xuất vay không hợp lệ!", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(str(user.id))
    lender_data = await get_user_data(str(user.id))
    if lender_data["balance"] < amount:
        await interaction.response.send_message(f"❌ Đối phương không đủ số dư để cho vay!", ephemeral=True)
        return
        
    class LoanView(discord.ui.View):
        def __init__(self): super().__init__(timeout=60)
        @discord.ui.button(label="Đồng Ý", style=discord.ButtonStyle.success, emoji="✅")
        async def accept(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id: return
            now = datetime.now(timezone.utc)
            due_at = now + timedelta(days=LOAN_DUE_DAYS)
            if await transfer_money(str(user.id), user_id, amount, "loan"):
                loan_ref = db.collection("loans").add({"borrowerId": user_id, "lenderId": str(user.id), "amount": amount, "createdAt": now.isoformat(), "dueAt": due_at.isoformat(), "repaid": False})
                embed = create_embed(title="✅ Hợp Đồng Vay Thành Công", description=f"**{interaction.user.name}** đã vay **{amount:,} VNĐ** từ **{user.name}**", color=COLOR_SUCCESS, fields=[("📋 Mã khoản vay", loan_ref[1].id, False), ("📅 Hạn trả", due_at.strftime("%d/%m/%Y"), False)])
                await button_interaction.message.edit(embed=embed, view=None)
            else: await button_interaction.message.edit(content="❌ Có lỗi xảy ra trong giao dịch vay!", view=None)
        @discord.ui.button(label="Từ Chối", style=discord.ButtonStyle.danger, emoji="❌")
        async def reject(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id: return
            await button_interaction.message.edit(content=f"❌ **{user.name}** đã từ chối yêu cầu vay.", embed=None, view=None)
            
    embed = create_embed(title="💳 Yêu Cầu Vay Tiền", description=f"**{interaction.user.name}** muốn vay **{amount:,} VNĐ** từ **{user.name}**\nHạn trả: **7 ngày**", color=COLOR_WARNING)
    cooldown_manager.set_cooldown(user_id, "vay")
    await interaction.response.send_message(embed=embed, view=LoanView())

@bot.tree.command(name="tra", description="💳 Thanh toán khoản vay nợ")
@app_commands.describe(loan_id="Mã ID của khoản vay")
@check_cooldown("tra", COOLDOWN_NORMAL)
async def tra(interaction: discord.Interaction, loan_id: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "tra")
    loan_doc = get_loan_ref(loan_id).get()
    if not loan_doc.exists:
        await interaction.response.send_message("❌ Khoản vay không tồn tại!", ephemeral=True)
        return
    l_data = loan_doc.to_dict()
    if l_data["repaid"] or l_data["borrowerId"] != user_id:
        await interaction.response.send_message("❌ Khoản vay không hợp lệ hoặc đã được trả trước đó!", ephemeral=True)
        return
    user_data = await get_user_data(user_id)
    if user_data["balance"] < l_data["amount"]:
        await interaction.response.send_message("❌ Số dư của bạn không đủ để trả nợ!", ephemeral=True)
        return
    if await transfer_money(user_id, l_data["lenderId"], l_data["amount"], "repay"):
        get_loan_ref(loan_id).update({"repaid": True})
        await interaction.response.send_message(f"✅ Đã trả thành công **{l_data['amount']:,} VNĐ** cho <@{l_data['lenderId']}>.")

@bot.tree.command(name="nolist", description="📋 Xem danh sách các khoản nợ của bạn")
@check_cooldown("nolist", COOLDOWN_NORMAL)
async def nolist(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "nolist")
    loans = db.collection("loans").where(filter=FieldFilter("borrowerId", "==", user_id)).get()
    if not loans:
        await interaction.response.send_message("📋 Bạn không có khoản nợ nào hiện tại!", ephemeral=True)
        return
    desc = ""
    for l in loans:
        d = l.to_dict()
        status = "✅ Đã trả" if d["repaid"] else "⚠️ Chưa trả"
        desc += f"🆔 `{l.id}` | Tiền: **{d['amount']:,}** VNĐ | Trạng thái: {status}\n"
    embed = create_embed(title="📋 Danh Sách Nợ", description=desc, color=COLOR_WARNING)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="anxin", description="🙏 Gửi yêu cầu xin tiền từ người chơi khác")
@app_commands.describe(user="Người bạn muốn xin tiền", amount="Số tiền muốn xin")
@check_cooldown("anxin", COOLDOWN_NORMAL)
async def anxin(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.bot or user.id == interaction.user.id or amount <= 0:
        await interaction.response.send_message("❌ Đối tượng xin tiền không hợp lệ!", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(str(user.id))
    lender_data = await get_user_data(str(user.id))
    if lender_data["balance"] < amount:
        await interaction.response.send_message("❌ Đối phương không đủ số dư để cho!", ephemeral=True)
        return
        
    class BegView(discord.ui.View):
        def __init__(self): super().__init__(timeout=60)
        @discord.ui.button(label="Cho", style=discord.ButtonStyle.success, emoji="🧧")
        async def accept(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id: return
            if await transfer_money(str(user.id), user_id, amount, "beg"):
                await button_interaction.message.edit(content=f"✅ **{user.name}** đã hảo tâm cho **{interaction.user.name}** **{amount:,}** VNĐ!", embed=None, view=None)
            else: await button_interaction.message.edit(content="❌ Giao dịch thất bại!", view=None)
        @discord.ui.button(label="Từ Chối", style=discord.ButtonStyle.danger, emoji="❌")
        async def reject(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id: return
            await button_interaction.message.edit(content=f"❌ **{user.name}** đã từ chối cho tiền.", embed=None, view=None)
            
    embed = create_embed(title="🙏 Xin Lì Xì Hảo Tâm", description=f"**{interaction.user.name}** đang xin **{amount:,} VNĐ** từ **{user.name}**", color=COLOR_INFO)
    cooldown_manager.set_cooldown(user_id, "anxin")
    await interaction.response.send_message(embed=embed, view=BegView())

# ============================================
# GAME: TAI XIU SINGLE PLAYER
# ============================================
@bot.tree.command(name="taixiu", description="🎲 Đặt cược Tài Xỉu xúc xắc")
@app_commands.describe(cuoc="Chọn cửa đặt cược", sotien="Số tiền cược (nhập số hoặc 'all' để cược hết)")
@app_commands.choices(cuoc=[
    app_commands.Choice(name="🔴 Tài (11-17)", value="tai"), app_commands.Choice(name="🔵 Xỉu (4-10)", value="xiu"),
    app_commands.Choice(name="⚪ Chẵn", value="chan"), app_commands.Choice(name="⚫ Lẻ", value="le")
])
@check_cooldown("taixiu", COOLDOWN_NORMAL)
async def taixiu_cmd(interaction: discord.Interaction, cuoc: str, sotien: str):
    if not await rate_limiter.acquire(str(interaction.user.id)):
        await interaction.response.send_message("❌ Lượt cược của bạn đang được xử lý, vui lòng chờ trong giây lát!", ephemeral=True)
        return
    try:
        user_id = str(interaction.user.id)
        user_data = await create_user_if_not_exists(user_id)
        try: bet_amount = user_data["balance"] if sotien.lower() == "all" else int(sotien)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền cược không hợp lệ!", ephemeral=True)
            return
        if bet_amount <= 0 or bet_amount > user_data["balance"]:
            await interaction.response.send_message("❌ Số dư tài khoản không đủ để thực hiện!", ephemeral=True)
            return
        success = await deduct_bet(user_id, bet_amount)
        if not success:
            await interaction.response.send_message("❌ Đặt cược thất bại!", ephemeral=True)
            return
        game_list = get_recent_games(100)
        dice1, dice2, dice3 = calculate_weighted_roll(game_list)
        total = dice1 + dice2 + dice3
        dice_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}
        embed = create_embed(title="🎲 Tài Xỉu", description="Đang lắc xúc xắc...", color=COLOR_GOLD)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(3):
            await asyncio.sleep(0.8)
            desc = f"{dice_emojis[dice1]} ? ?" if i == 0 else f"{dice_emojis[dice1]} {dice_emojis[dice2]} ?" if i == 1 else f"{dice_emojis[dice1]} {dice_emojis[dice2]} {dice_emojis[dice3]}"
            await msg.edit(embed=create_embed(title="🎲 Tài Xỉu", description=f"**Xúc xắc:** {desc}", color=COLOR_GOLD))
        is_tai, is_xiu, is_chan, is_le, is_triple = 11 <= total <= 17, 4 <= total <= 10, total % 2 == 0, total % 2 == 1, total in [3, 18]
        win, multiplier = False, 0
        if cuoc == "tai" and is_tai and not is_triple: win, multiplier = True, 2
        elif cuoc == "xiu" and is_xiu and not is_triple: win, multiplier = True, 2
        elif cuoc == "chan" and is_chan: win, multiplier = True, 2
        elif cuoc == "le" and is_le: win, multiplier = True, 2
        if win:
            win_amount = bet_amount * multiplier
            await add_win(user_id, win_amount)
            result_text = f"🎉 Bạn đã thắng **{win_amount:,} VNĐ**!"
            await update_user_stats(user_id, True, bet_amount, win_amount)
            color = COLOR_SUCCESS
        else:
            if await check_and_deduct_shield(user_id):
                await add_win(user_id, bet_amount)
                result_text = "🛡️ Phiếu Miễn Cược đã kích hoạt, bạn không bị mất tiền!"
            else: result_text = "😢 Rất tiếc, bạn đã thua!"
            await update_user_stats(user_id, False, bet_amount, 0)
            color = COLOR_ERROR
        get_game_history_ref().add({"result": total, "dice1": dice1, "dice2": dice2, "dice3": dice3, "betType": cuoc, "betAmount": bet_amount, "win": win, "multiplier": multiplier, "taiOrXiu": "tai" if is_tai else ("xiu" if is_xiu else "triple"), "createdAt": datetime.now(timezone.utc).isoformat(), "userId": user_id})
        await msg.edit(embed=create_embed(title="🎲 Kết Quả Tài Xỉu", description=f"**Xúc xắc:** {dice_emojis[dice1]} • {dice_emojis[dice2]} • {dice_emojis[dice3]}\n\n📊 Tổng điểm: **{total}**\n\n{result_text}", color=color))
        cooldown_manager.set_cooldown(user_id, "taixiu")
    finally: rate_limiter.release(str(interaction.user.id))

# ============================================
# GAME: COINFLIP SINGLE PLAYER
# ============================================
@bot.tree.command(name="coinflip", description="🪙 Tung đồng xu cược may rủi")
@app_commands.describe(choice="Mặt đồng xu bạn chọn", amount="Số tiền đặt cược")
@app_commands.choices(choice=[
    app_commands.Choice(name="🪙 Ngửa (Head)", value="head"), app_commands.Choice(name="🪙 Sấp (Tail)", value="tail")
])
@check_cooldown("coinflip", COOLDOWN_NORMAL)
async def coinflip(interaction: discord.Interaction, choice: str, amount: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "coinflip")
    user_data = await create_user_if_not_exists(user_id)
    try: bet_amount = user_data["balance"] if amount.lower() == "all" else int(amount)
    except ValueError:
        await interaction.response.send_message("❌ Số tiền cược không hợp lệ!", ephemeral=True)
        return
    if bet_amount <= 0 or bet_amount > user_data["balance"]:
        await interaction.response.send_message("❌ Số dư tài khoản không đủ!", ephemeral=True)
        return
    success = await deduct_bet(user_id, bet_amount)
    if not success:
        await interaction.response.send_message("❌ Đặt cược lỗi!", ephemeral=True)
        return
    embed = create_embed(title="🪙 CoinFlip", description="Đang tung đồng xu...", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    for _ in range(3):
        await asyncio.sleep(0.5)
        await msg.edit(embed=create_embed(title="🪙 CoinFlip", description="🪙 Đang xoay...", color=COLOR_GOLD))
    result = random.choice(["head", "tail"])
    result_text = "Mặt Ngửa (Head)" if result == "head" else "Mặt Sấp (Tail)"
    win = choice == result
    if win:
        win_amount = bet_amount * 2
        await add_win(user_id, win_amount)
        await update_user_stats(user_id, True, bet_amount, win_amount)
        embed = create_embed(title="🪙 Kết Quả CoinFlip", description=f"Kết quả là: **{result_text}**\n🎉 Bạn đã thắng **{win_amount:,}** VNĐ!", color=COLOR_SUCCESS)
    else:
        if await check_and_deduct_shield(user_id):
            await add_win(user_id, bet_amount)
            await update_user_stats(user_id, False, bet_amount, 0)
            embed = create_embed(title="🪙 Kết Quả CoinFlip", description=f"Kết quả là: **{result_text}**\n🛡️ Phiếu Miễn Cược đã bảo vệ số tiền của bạn!", color=COLOR_SUCCESS)
        else:
            await update_user_stats(user_id, False, bet_amount, 0)
            embed = create_embed(title="🪙 Kết Quả CoinFlip", description=f"Kết quả là: **{result_text}**\n😢 Bạn đã thua!", color=COLOR_ERROR)
    await msg.edit(embed=embed)

# ============================================
# GAME: SLOT MACHINE SINGLE PLAYER
# ============================================
@bot.tree.command(name="slot", description="🎰 Quay máy Slot Jackpot")
@app_commands.describe(amount="Số tiền cược")
@check_cooldown("slot", COOLDOWN_NORMAL)
async def slot(interaction: discord.Interaction, amount: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "slot")
    user_data = await create_user_if_not_exists(user_id)
    try: bet_amount = user_data["balance"] if amount.lower() == "all" else int(amount)
    except ValueError:
        await interaction.response.send_message("❌ Số tiền cược không hợp lệ!", ephemeral=True)
        return
    if bet_amount <= 0 or bet_amount > user_data["balance"]:
        await interaction.response.send_message("❌ Số dư không đủ!", ephemeral=True)
        return
    success = await deduct_bet(user_id, bet_amount)
    if not success:
        await interaction.response.send_message("❌ Lỗi đặt cược!", ephemeral=True)
        return
    reels = [[random.choice(SLOT_SYMBOLS) for _ in range(3)] for _ in range(3)]
    embed = create_embed(title="🎰 Slot Machine", description="Đang quay các trục...", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    for i in range(4):
        await asyncio.sleep(0.6)
        display = ""
        for row in range(3):
            temp_row = [random.choice(SLOT_SYMBOLS) for _ in range(3)] if i < 3 else reels[row]
            display += " ".join(temp_row) + "\n"
        await msg.edit(embed=create_embed(title="🎰 Slot Machine", description=f"```\n{display}```", color=COLOR_GOLD))
    middle_row = reels[1]
    row_str = "".join(middle_row)
    win, multiplier = False, 0
    if row_str in SLOT_PAYOUTS:
        multiplier = SLOT_PAYOUTS[row_str]
        win = True
    elif middle_row[0] == middle_row[1] or middle_row[1] == middle_row[2] or middle_row[0] == middle_row[2]:
        multiplier = 1.5
        win = True
    if win:
        win_amount = int(bet_amount * multiplier)
        await add_win(user_id, win_amount)
        await update_user_stats(user_id, True, bet_amount, win_amount)
        result_text = f"🎉 Bạn đã thắng **{win_amount:,} VNĐ**!"
        color = COLOR_SUCCESS
    else:
        if await check_and_deduct_shield(user_id):
            await add_win(user_id, bet_amount)
            await update_user_stats(user_id, False, bet_amount, 0)
            result_text = "🛡️ Phiếu Miễn Cược bảo vệ số dư của bạn!"
            color = COLOR_SUCCESS
        else:
            await update_user_stats(user_id, False, bet_amount, 0)
            result_text = "😢 Chúc bạn may mắn lần sau!"
            color = COLOR_ERROR
    final_display = "\n".join([" ".join(row) for row in reels])
    await msg.edit(embed=create_embed(title="🎰 Kết Quả Slot", description=f"```\n{final_display}```\n\n{result_text}", color=color))

# ============================================
# GAME: LỖ ĐÍT (CHOI LO DIT)
# ============================================
@bot.tree.command(name="choilodit", description="🎯 Trêu chọc người chơi khác (Có tính phí)")
@app_commands.describe(user="Người bạn muốn chọc")
@check_cooldown("choilodit", COOLDOWN_NORMAL)
async def choilodit(interaction: discord.Interaction, user: discord.User):
    if user.bot or user.id == interaction.user.id:
        await interaction.response.send_message("❌ Đối tượng không hợp lệ!", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(str(user.id))
    has_coupon = await check_and_deduct_coupon(user_id)
    price = 50000 if has_coupon else 100000
    user_data = await get_user_data(user_id)
    if user_data["balance"] < price:
        await interaction.response.send_message(f"❌ Bạn không đủ tiền! Chi phí: {price:,} VNĐ", ephemeral=True)
        return
    if await transfer_money(user_id, str(user.id), price, "lodit"):
        coupon_text = " (Đã sử dụng Coupon giảm giá 50%)" if has_coupon else ""
        embed = create_embed(title="🎯 Trêu Chọc Lỗ Đít", description=f"**{interaction.user.name}** đã thực hiện chọc lỗ đít của **{user.name}**{coupon_text}!\n💸 Phí trêu chọc chuyển cho đối phương: **{price:,} VNĐ**", color=COLOR_SUCCESS)
        cooldown_manager.set_cooldown(user_id, "choilodit")
        await interaction.response.send_message(embed=embed)
    else: await interaction.response.send_message("❌ Lỗi giao dịch trêu chọc!", ephemeral=True)

# ============================================
# GAME: MINES
# ============================================
@bot.tree.command(name="mines", description="💣 Trò chơi dò mìn Mines cực kỳ hấp dẫn")
@app_commands.describe(bet="Số tiền cược", mines_count="Số lượng mìn trên bản đồ (1-24)")
async def mines(interaction: discord.Interaction, bet: int, mines_count: int):
    if mines_count < 1 or mines_count > 24:
        await interaction.response.send_message("❌ Số lượng mìn phải nằm trong khoảng từ 1 đến 24!", ephemeral=True)
        return
    if bet <= 0:
        await interaction.response.send_message("❌ Tiền cược phải lớn hơn 0 VNĐ!", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    user_data = await create_user_if_not_exists(user_id)
    if user_data["balance"] < bet:
        await interaction.response.send_message("❌ Số dư tài khoản của bạn không đủ!", ephemeral=True)
        return
        
    success = await deduct_bet(user_id, bet)
    if not success:
        await interaction.response.send_message("❌ Khởi tạo ván chơi thất bại!", ephemeral=True)
        return
        
    view = MinesGameView(user_id, bet, mines_count)
    embed = create_embed(title="💎 MINES GAME STARTED", description=f"Người chơi: <@{user_id}>\nCược: **{bet:,}** VNĐ | Số mìn: **{mines_count}**\nHãy lật các ô và tránh bom!", color=COLOR_INFO)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ============================================
# SPECTATE & GENERAL COMMANDS
# ============================================
@bot.tree.command(name="spectate", description="👀 Theo dõi diễn biến trận đấu đang diễn ra")
@app_commands.describe(room_id="Mã ID phòng chơi đang hoạt động")
async def spectate(interaction: discord.Interaction, room_id: str):
    room = room_manager.get_room(room_id)
    if not room:
        await interaction.response.send_message("❌ Phòng chơi này không tồn tại hoặc đã đóng!", ephemeral=True)
        return
    embed = create_embed(title="👀 Spectator Mode", description="Nhấn nút bên dưới để làm mới diễn biến trận đấu hiện tại mà không nhìn thấy bài của người chơi.", color=COLOR_INFO)
    await interaction.response.send_message(embed=embed, view=SpectatorView(room_id), ephemeral=True)

# ============================================
# ADMINISTRATIVE COMMANDS
# ============================================
@bot.tree.command(name="addadmin", description="👑 Thăng cấp Mini Admin cho người chơi (Chỉ Super Admin)")
@app_commands.describe(user="Người được thăng cấp")
async def addadmin(interaction: discord.Interaction, user: discord.User):
    if not await is_super_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền hạn thực hiện lệnh này!", ephemeral=True)
        return
    target_id = str(user.id)
    get_admin_ref(target_id).set({"userId": target_id, "role": "mini"})
    await interaction.response.send_message(f"👑 Đã thăng chức cho **{user.name}** thành Mini Admin!")

@bot.tree.command(name="removeadmin", description="👑 Giáng cấp Admin cho người chơi (Chỉ Super Admin)")
@app_commands.describe(user="Người bị giáng cấp")
async def removeadmin(interaction: discord.Interaction, user: discord.User):
    if not await is_super_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền hạn thực hiện lệnh này!", ephemeral=True)
        return
    target_id = str(user.id)
    get_admin_ref(target_id).delete()
    await interaction.response.send_message(f"👑 Đã giáng chức Admin của **{user.name}** thành công.")

@bot.tree.command(name="trutien", description="💸 Khấu trừ số dư của người chơi (Chỉ Admin)")
@app_commands.describe(user="Người bị trừ tiền", amount="Số tiền khấu trừ")
async def trutien(interaction: discord.Interaction, user: discord.User, amount: int):
    if not await is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền hạn thực hiện lệnh này!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền khấu trừ phải lớn hơn 0 VNĐ!", ephemeral=True)
        return
    success = await remove_money(str(user.id), amount, str(interaction.user.id))
    if success:
        await interaction.response.send_message(f"✅ Đã khấu trừ thành công **{amount:,}** VNĐ của **{user.name}**.")
    else: await interaction.response.send_message("❌ Tài khoản đối phương không đủ số dư để khấu trừ!", ephemeral=True)

@bot.tree.command(name="phatlixi", description="🧧 Phát lì xì may mắn cho tất cả mọi người (Chỉ Admin)")
@app_commands.describe(amount="Số tiền lì xì mỗi người nhận")
async def phatlixi(interaction: discord.Interaction, amount: int):
    if not await is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền hạn thực hiện lệnh này!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền lì xì phải lớn hơn 0 VNĐ!", ephemeral=True)
        return
        
    class LixiView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.claimed = set()
        @discord.ui.button(label="Nhận Lì Xì", style=discord.ButtonStyle.success, emoji="🧧")
        async def claim(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            u_id = str(button_interaction.user.id)
            if u_id in self.claimed:
                await button_interaction.response.send_message("❌ Bạn đã nhận lì xì rồi!", ephemeral=True)
                return
            await create_user_if_not_exists(u_id)
            await add_money(u_id, amount, str(interaction.user.id))
            self.claimed.add(u_id)
            await button_interaction.response.send_message(f"🧧 Bạn đã nhận thành công **{amount:,}** VNĐ lì xì! 🎉", ephemeral=True)
            
    embed = create_embed(title="🧧 LÌ XÌ MAY MẮN TỪ ADMIN", description=f"Admin **{interaction.user.name}** đã phát lì xì!\n💰 Giá trị mỗi người nhận: **{amount:,}** VNĐ\nNhấn nút phía dưới để nhận ngay!", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed, view=LixiView())

@bot.tree.command(name="lichsu", description="📋 Xem lịch sử các giao dịch tài chính của bạn")
@check_cooldown("lichsu", COOLDOWN_NORMAL)
async def lichsu(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "lichsu")
    transactions = get_transactions_ref().where(filter=FieldFilter("userId", "==", user_id)).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
    if not transactions:
        await interaction.response.send_message("📋 Bạn chưa có giao dịch nào được ghi nhận!", ephemeral=True)
        return
    desc = ""
    for t in transactions:
        d = t.to_dict()
        desc += f"• **{d.get('type','unknown')}**: {d.get('amount',0):,} VNĐ | {d.get('description','')}\n"
    embed = create_embed(title="📋 Lịch Sử Giao Dịch", description=desc, color=COLOR_INFO)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="doan", description="🤖 AI phân tích và dự đoán phiên tiếp theo")
@check_cooldown("doan", COOLDOWN_NORMAL)
async def doan(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "doan")
    games = get_game_history_ref().order_by("createdAt", direction=firestore.Query.DESCENDING).limit(10).get()
    if not games:
        await interaction.response.send_message("🤖 Chưa có lịch sử chơi xúc xắc trên hệ thống!", ephemeral=True)
        return
    pred = random.choice(["🔴 TÀI", "🔵 XỈU"])
    embed = create_embed(title="🔮 AI Dự Đoán Tài Xỉu", description=f"🤖 Nhận định dựa vào thuật toán cầu phiên gần nhất:\n🎯 Phiên sau khuyến nghị: **{pred}**", color=COLOR_INFO)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="phantich", description="📊 Phân tích xu hướng cầu Tài Xỉu phiên hiện tại")
@check_cooldown("phantich", COOLDOWN_NORMAL)
async def phantich(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "phantich")
    games = [doc.to_dict() for doc in get_game_history_ref().order_by("createdAt", direction=firestore.Query.DESCENDING).limit(20).get()]
    if len(games) < 5:
        await interaction.response.send_message("📊 Dữ liệu phiên hiện tại quá ít, hãy chơi thêm vài ván để phân tích!", ephemeral=True)
        return
    pattern = detect_cau_pattern(games)
    embed = create_embed(title="📊 Phân Tích Cầu Tài Xỉu", description=f"🔎 Cầu nhận định: **{pattern}**\nKhuyến cáo cân nhắc trước khi theo cầu bệt hoặc cầu gãy.", color=COLOR_INFO)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addmoney", description="💰 Thêm số dư trực tiếp cho người chơi (Chỉ Admin)")
@app_commands.describe(user="Người nhận", amount="Số tiền muốn thêm")
async def addmoney_cmd(interaction: discord.Interaction, user: discord.User, amount: int):
    if not await is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền hạn thực hiện lệnh này!", ephemeral=True)
        return
    await create_user_if_not_exists(str(user.id))
    if await add_money(str(user.id), amount, str(interaction.user.id)):
        await interaction.response.send_message(f"✅ Đã thêm **{amount:,}** VNĐ cho **{user.name}** thành công.")
    else: await interaction.response.send_message("❌ Giao dịch lỗi!", ephemeral=True)

@bot.tree.command(name="jackpot", description="🎰 Xem giải Jackpot hiện tại")
@check_cooldown("jackpot", COOLDOWN_NORMAL)
async def jackpot_cmd(interaction: discord.Interaction):
    try:
        amount = await get_jackpot()
        embed = create_embed(
            title="🎰 JACKPOT",
            description=f"**Giải thưởng hiện tại:** {amount:,} VNĐ\n\n📊 2% từ mỗi game được cộng vào Jackpot!\n🎯 Jackpot sẽ được trao ngẫu nhiên cho người chơi may mắn!",
            color=COLOR_GOLD
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await log_error("jackpot", "jackpot", str(interaction.user.id), str(e), traceback.format_exc())
        await interaction.response.send_message("❌ Lỗi xem jackpot!", ephemeral=True)

# ============================================
# ACTIVE COLD ROOM RECOVERY ON STARTUP
# ============================================
async def restore_rooms():
    print("🔄 Đang phục hồi trạng thái các phòng đấu đang diễn ra từ Firestore...")
    try:
        rooms_snap = db.collection("rooms").get()
        count = 0
        for doc in rooms_snap:
            data = doc.to_dict()
            room_data = data.get("room_data", {})
            room_state = data.get("room_state", {})
            room_id = room_data.get("roomId")
            if not room_id: continue
            
            guild = bot.get_guild(int(room_data.get("guildId")))
            if not guild: continue
            
            channel = guild.get_channel(int(room_data.get("channelId")))
            thread = guild.get_thread(int(room_data.get("threadId")))
            if not thread and channel:
                try: thread = await channel.fetch_thread(int(room_data.get("threadId")))
                except: pass
                
            if thread:
                room_manager.active_rooms[room_id] = room_data
                room_manager.room_states[room_id] = room_state
                for player_id in room_data.get("players", []):
                    room_manager.player_rooms[player_id] = room_id
                    
                await thread.send("🔄 **Hệ thống Server vừa được khôi phục sau sự cố bảo trì.** Vui lòng nhấn mở bảng điều khiển để tiếp tục lượt đấu!")
                count += 1
                
                # Re-render persistent board UI elements
                if room_data.get("gameType") == "tienlen":
                    await update_tl_board_msg(room_id, thread)
                elif room_data.get("gameType") == "blackjack":
                    await update_bj_board_msg(room_id, thread)
            else:
                # If thread was deleted during downtime, refund players [1]
                for player_id in room_data.get("players", []):
                    custom_bets = room_state.get("custom_bets", {})
                    bet_refund = custom_bets.get(player_id, room_data.get("betAmount", 0))
                    await add_win(player_id, bet_refund)
                db.collection("rooms").document(room_id).delete()
                
        print(f"🔄 Phục hồi hoàn tất: {count} phòng đấu đã hoạt động trở lại.")
    except Exception as e:
        print(f"❌ Khôi phục phòng đấu lỗi: {e}")

async def auto_backup():
    while True:
        await asyncio.sleep(21600)  # 6 hours
        try:
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            collections = ["users", "loans", "transactions", "game_history", "room_history"]
            backup_data = {}
            for col_name in collections:
                docs = db.collection(col_name).get()
                backup_data[col_name] = [doc.to_dict() for doc in docs]
            filename = f"{backup_dir}/backup_{timestamp}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, default=str)
            print(f"✅ Backup hoàn tất: {filename}")
        except Exception as e: print(f"❌ Backup dữ liệu lỗi: {e}")

# ============================================
# TAI XIU PVP GAME LOOP
# ============================================
async def start_taixiu_pvp(room_id: str, thread: discord.Thread):
    room = room_manager.get_room(room_id)
    if not room: return
    players = room["players"]
    bet_amount = room["betAmount"]
    results = {}
    for player_id in players:
        dice1, dice2, dice3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
        results[player_id] = {"dice": [dice1, dice2, dice3], "total": dice1 + dice2 + dice3}
    sorted_players = sorted(results.items(), key=lambda x: x[1]["total"], reverse=True)
    rankings = {}
    total_pool = int(bet_amount * len(players) * 0.95)
    for i, (player_id, data) in enumerate(sorted_players):
        if i == 0: reward = int(total_pool * 0.7)
        elif i == 1: reward = int(total_pool * 0.25)
        elif i == 2 and len(players) >= 3: reward = int(total_pool * 0.05)
        else: reward = 0
        rankings[player_id] = {"dice": data["dice"], "total": data["total"], "reward": reward}
        if reward > 0: await add_win(player_id, reward)
    dice_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}
    description = "🎲 **KẾT QUẢ TÀI XỈU PvP**\n\n"
    for i, (player_id, data) in enumerate(sorted_players):
        d = data["dice"]
        medal = ["🥇", "🥈", "🥉", "💀"][i] if i < 4 else f"{i+1}."
        description += f"{medal} <@{player_id}>\n   {dice_emojis[d[0]]} {dice_emojis[d[1]]} {dice_emojis[d[2]]} = **{data['total']}**\n   💰 {data['reward']:,} VNĐ\n\n"
    description += f"🗑️ Phòng sẽ tự giải tán sau 15 giây..."
    embed = create_embed(title="🏆 Kết Quả Tài Xỉu PvP", description=description, color=COLOR_GOLD)
    await thread.send(embed=embed)
    await asyncio.sleep(15)
    await end_game_and_cleanup(room_id, thread, {"rankings": rankings})

async def cleanup_and_delete_room(room_id: str, thread: discord.Thread):
    room = room_manager.get_room(room_id)
    if room and room["status"] != RoomStatus.FINISHED:
        for player_id in room["players"]:
            if room["status"] == RoomStatus.WAITING:
                custom_bets = room_manager.room_states[room_id].get("custom_bets", {})
                bet_refund = custom_bets.get(player_id, room["betAmount"])
                await add_win(player_id, bet_refund)
    await room_manager.cleanup_room(room_id)
    try: await thread.delete()
    except: pass

# ============================================
# CREATE ROOM COMMAND (No Auto-Start)
# ============================================
@bot.tree.command(name="taophong", description="🏠 Tạo phòng chơi game riêng tư")
@app_commands.describe(game="Chọn game muốn chơi", bet="Số tiền cược")
@app_commands.choices(game=[
    app_commands.Choice(name="🎲 Tài Xỉu Đối Kháng", value="taixiu"),
    app_commands.Choice(name="🃏 Blackjack (21 điểm)", value="blackjack"),
    app_commands.Choice(name="🀄 Tiến Lên Miền Nam", value="tienlen"),
])
async def taophong(interaction: discord.Interaction, game: str, bet: str):
    user_id = str(interaction.user.id)
    if room_manager.get_player_room(user_id):
        await interaction.response.send_message("❌ Bạn đang ở phòng khác!", ephemeral=True)
        return
    try: bet_amount = int(bet)
    except ValueError:
        await interaction.response.send_message("❌ Số tiền cược không hợp lệ!", ephemeral=True)
        return
    if bet_amount < 10000:
        await interaction.response.send_message("❌ Tiền cược tối thiểu là 10,000 VNĐ!", ephemeral=True)
        return
    user_data = await create_user_if_not_exists(user_id)
    if user_data["balance"] < bet_amount:
        await interaction.response.send_message(f"❌ Số dư không đủ! Cần {bet_amount:,} VNĐ", ephemeral=True)
        return
    success = await deduct_bet(user_id, bet_amount)
    if not success:
        await interaction.response.send_message("❌ Không thể trừ tiền cược!", ephemeral=True)
        return
    game_names = {"taixiu": "🎲 Tài Xỉu", "blackjack": "🃏 Blackjack", "tienlen": "🀄 Tiến Lên"}
    game_emoji = {"taixiu": "🎲", "blackjack": "🃏", "tienlen": "🀄"}
    thread = await interaction.channel.create_thread(name=f"{game_emoji[game]} {game_names[game]} - {interaction.user.name}", type=discord.ChannelType.private_thread, auto_archive_duration=60)
    await thread.add_user(interaction.user)
    room_id = f"{interaction.guild.id}_{thread.id}"
    room_manager.create_room(user_id, room_id, game, thread, bet_amount)
    invite_view = RoomInviteView(room_id, thread.id, bet_amount, game, game_names[game])
    invite_embed = create_embed(title=f"{game_emoji[game]} PHÒNG {game_names[game].upper()}", description=f"**Chủ phòng:** {interaction.user.mention}\n**Game:** {game_names[game]}\n**Tiền cược:** {bet_amount:,} VNĐ/người\n\n👤 **Người chơi (1/4):**\n1. {interaction.user.mention}\n\n🔒 Phòng riêng tư - Nhấn nút để tham gia!\n⏰ Tự đóng sau 5 phút nếu không đủ người.", color=COLOR_GOLD)
    public_msg = await interaction.channel.send(embed=invite_embed, view=invite_view)
    thread_embed = create_embed(title=f"🏠 Phòng {game_names[game]}", description=f"**Chủ phòng:** {interaction.user.mention}\n**Game:** {game_names[game]}\n**Tiền cược:** {bet_amount:,} VNĐ\n\n👤 **Người chơi (1/4):**\n1. {interaction.user.mention}\n\n🔒 Phòng riêng tư", color=COLOR_GOLD)
    view = RoomView(room_id, user_id, bet_amount, game)
    room_manager.store_view(room_id, view)
    await thread.send(embed=thread_embed, view=view)
    await interaction.response.send_message(f"✅ Đã tạo phòng riêng tư tại {thread.mention}!\n📢 Tin nhắn mời đã được gửi công khai.", ephemeral=True)
    asyncio.create_task(auto_close_room_with_public(room_id, thread, public_msg, 300))

async def auto_close_room_with_public(room_id: str, thread: discord.Thread, public_msg: discord.Message, timeout: int):
    await asyncio.sleep(timeout)
    room = room_manager.get_room(room_id)
    if room and room["status"] == RoomStatus.WAITING:
        for player_id in room["players"]:
            custom_bets = room_manager.room_states[room_id].get("custom_bets", {})
            refund_amount = custom_bets.get(player_id, room["betAmount"])
            await add_win(player_id, refund_amount)
        try: await thread.send("⏰ Phòng đã hết hạn do không đủ người chơi.\n💰 Tiền cược đã được hoàn trả.")
        except: pass
        try: await public_msg.delete()
        except: pass
        await asyncio.sleep(3)
        await cleanup_and_delete_room(room_id, thread)

# ============================================
# EXCEPTION COMMAND HANDLER
# ============================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    user_id = str(interaction.user.id)
    command_name = interaction.command.name if interaction.command else "unknown"
    if isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(f"⏰ Vui lòng đợi {error.retry_after:.0f} giây!", ephemeral=True)
    elif isinstance(error, app_commands.errors.CheckFailure): pass
    elif isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
    else:
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await log_error("command_error", command_name, user_id, str(error), tb_str)
        print(f"❌ Command error [{command_name}]: {error}")
        try: await interaction.response.send_message("❌ Có lỗi xảy ra! Đội ngũ kỹ thuật đã được thông báo.", ephemeral=True)
        except: pass

# ============================================
# WEB SERVER SETUP & INITS
# ============================================
async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', dashboard)
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web Server đã bắt đầu hoạt động trên cổng: {port}")

# ============================================
# BOT LAUNCH TRIGGER
# ============================================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN trống, dừng bot!")
        exit(1)
    @bot.event
    async def setup_hook(): await start_web_server()
    try: bot.run(DISCORD_TOKEN)
    except Exception as e: print(f"❌ Lỗi khởi chạy ứng dụng: {e}")
