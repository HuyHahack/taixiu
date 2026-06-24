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
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
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
warnings.filterwarnings('ignore')

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
# CONSTANTS
# ============================================
DEFAULT_BALANCE = 100000
DAILY_REWARD = 100000
LOAN_DUE_DAYS = 7
COOLDOWN_NORMAL = 10
COOLDOWN_DAILY = 86400

# ============================================
# EMOJI CONSTANTS
# ============================================
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
EMOJI_CRYSTAL = "💠"
EMOJI_MONEY_BAG = "💰"
EMOJI_UP = "📈"
EMOJI_DOWN = "📉"
EMOJI_CALENDAR = "📅"
EMOJI_SHIELD = "🛡️"
EMOJI_TICKET = "📄"
EMOJI_TAI = "🔴"
EMOJI_XIU = "🔵"
EMOJI_CHAN = "⚪"
EMOJI_LE = "⚫"

# ============================================
# COLOR CONSTANTS
# ============================================
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
COLOR_YELLOW = 0xFFFF00
COLOR_BLACK = 0x000000

PROFILE_COLORS = {
    "🔴 Đỏ": 0xFF0000,
    "🟢 Xanh lá": 0x00FF00,
    "🔵 Xanh dương": 0x3498DB,
    "🟣 Tím": 0x800080,
    "🟡 Vàng": 0xFFD700,
    "⚫ Đen": 0x000000
}

# ============================================
# SLOT SYMBOLS
# ============================================
SLOT_SYMBOLS = ["🍒", "🍋", "⭐", "💎"]
SLOT_PAYOUTS = {
    "💎💎💎": 20,
    "⭐⭐⭐": 10,
    "🍒🍒🍒": 5,
    "🍋🍋🍋": 3,
}

# ============================================
# TAI XIU PAYOUTS
# ============================================
SPECIFIC_NUMBER_PAYOUTS = {
    3: 30, 18: 30,
    4: 12, 17: 12,
    5: 8, 16: 8,
    6: 6, 15: 6,
    7: 5, 14: 5,
    8: 4, 13: 4,
    9: 3, 12: 3,
    10: 2, 11: 2
}

# ============================================
# BADGE CONSTANTS
# ============================================
BADGE_DAI_GIA = 10_000_000
BADGE_TY_PHU = 1_000_000_000
BADGE_TRIEU_PHU = 1_000_000
BADGE_CAO_THU = 500
BADGE_STREAK_GOD = 20

# ============================================
# DATABASE HELPERS
# ============================================
def get_user_ref(user_id: str):
    return db.collection("users").document(str(user_id))

def get_admin_ref(user_id: str):
    return db.collection("admins").document(str(user_id))

def get_loan_ref(loan_id: str):
    return db.collection("loans").document(str(loan_id))

def get_transactions_ref():
    return db.collection("transactions")

def get_game_history_ref():
    return db.collection("game_history")

def get_logs_ref():
    return db.collection("logs")

def get_red_packets_ref():
    return db.collection("red_packets")

async def get_user_data(user_id: str) -> Optional[Dict]:
    doc = get_user_ref(user_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

async def create_user_if_not_exists(user_id: str) -> Dict:
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        now = datetime.now(timezone.utc)
        user_data = {
            "userId": str(user_id),
            "balance": DEFAULT_BALANCE,
            "totalGames": 0,
            "totalWins": 0,
            "totalLosses": 0,
            "currentWinStreak": 0,
            "currentLoseStreak": 0,
            "bestWinStreak": 0,
            "biggestWin": 0,
            "biggestLoss": 0,
            "totalMoneyWon": 0,
            "totalMoneyLost": 0,
            "freeBetShield": 0,
            "discountCouponUses": 0,
            "profileColor": "🔵 Xanh dương",
            "dailyLastClaim": None,
            "createdAt": now
        }
        user_ref.set(user_data)
        print(f"✅ Created new user: {user_id}")
        return user_data
    return user_doc.to_dict()

async def is_admin(user_id: str) -> bool:
    if str(user_id) == SUPER_ADMIN_ID:
        return True
    admin_doc = get_admin_ref(str(user_id)).get()
    return admin_doc.exists

async def is_super_admin(user_id: str) -> bool:
    return str(user_id) == SUPER_ADMIN_ID

async def check_loans_overdue(user_id: str) -> Tuple[bool, List[Dict]]:
    loans_ref = db.collection("loans")
    now = datetime.now(timezone.utc)
    
    loans = loans_ref.where(
        filter=FieldFilter("borrowerId", "==", str(user_id))
    ).where(
        filter=FieldFilter("repaid", "==", False)
    ).get()
    
    overdue_loans = []
    for loan in loans:
        loan_data = loan.to_dict()
        due_at = loan_data.get("dueAt")
        if due_at and isinstance(due_at, datetime) and due_at < now:
            overdue_loans.append(loan_data)
    
    return len(overdue_loans) > 0, overdue_loans

async def add_log(log_type: str, user_id: str, amount: int, target_id: Optional[str] = None, description: Optional[str] = None):
    log_data = {
        "type": log_type,
        "userId": str(user_id),
        "amount": amount,
        "targetId": str(target_id) if target_id else None,
        "description": description,
        "timestamp": datetime.now(timezone.utc)
    }
    get_logs_ref().add(log_data)

async def add_transaction(transaction_type: str, user_id: str, amount: int, target_id: Optional[str] = None, description: Optional[str] = None):
    transaction_data = {
        "type": transaction_type,
        "userId": str(user_id),
        "amount": amount,
        "targetId": str(target_id) if target_id else None,
        "description": description,
        "timestamp": datetime.now(timezone.utc)
    }
    get_transactions_ref().add(transaction_data)

async def update_user_stats(user_id: str, is_win: bool, bet_amount: int, win_amount: int):
    """Update user stats directly"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"❌ User {user_id} not found for stats update")
        return
    
    user_data = user_doc.to_dict()
    user_data["totalGames"] = user_data.get("totalGames", 0) + 1
    
    if is_win:
        user_data["totalWins"] = user_data.get("totalWins", 0) + 1
        user_data["currentWinStreak"] = user_data.get("currentWinStreak", 0) + 1
        user_data["currentLoseStreak"] = 0
        if user_data["currentWinStreak"] > user_data.get("bestWinStreak", 0):
            user_data["bestWinStreak"] = user_data["currentWinStreak"]
        if win_amount > user_data.get("biggestWin", 0):
            user_data["biggestWin"] = win_amount
        user_data["totalMoneyWon"] = user_data.get("totalMoneyWon", 0) + win_amount
    else:
        user_data["totalLosses"] = user_data.get("totalLosses", 0) + 1
        user_data["currentLoseStreak"] = user_data.get("currentLoseStreak", 0) + 1
        user_data["currentWinStreak"] = 0
        if bet_amount > user_data.get("biggestLoss", 0):
            user_data["biggestLoss"] = bet_amount
        user_data["totalMoneyLost"] = user_data.get("totalMoneyLost", 0) + bet_amount
    
    user_ref.set(user_data)
    print(f"📊 Stats updated: games={user_data['totalGames']}, wins={user_data['totalWins']}, losses={user_data['totalLosses']}")

# ============================================
# COOLDOWN MANAGER
# ============================================
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
# DISCORD BOT SETUP
# ============================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ============================================
# HELPER FUNCTIONS
# ============================================
def create_embed(title: str, description: str = "", color: int = COLOR_PRIMARY, fields: List[Tuple[str, str, bool]] = None, thumbnail_url: str = None, footer_text: str = None, timestamp: bool = True) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc) if timestamp else None)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer_text:
        embed.set_footer(text=footer_text)
    return embed

async def transfer_money(from_id: str, to_id: str, amount: int, transaction_type: str = "transfer") -> bool:
    """Transfer money directly"""
    from_ref = get_user_ref(from_id)
    to_ref = get_user_ref(to_id)
    
    from_doc = from_ref.get()
    to_doc = to_ref.get()
    
    if not from_doc.exists:
        print(f"❌ Sender {from_id} not found")
        return False
    if not to_doc.exists:
        print(f"❌ Receiver {to_id} not found")
        return False
    
    from_data = from_doc.to_dict()
    to_data = to_doc.to_dict()
    
    if from_data.get("balance", 0) < amount:
        print(f"❌ Insufficient balance: {from_data.get('balance', 0)} < {amount}")
        return False
    
    from_data["balance"] = from_data["balance"] - amount
    to_data["balance"] = to_data.get("balance", 0) + amount
    
    from_ref.set(from_data)
    to_ref.set(to_data)
    
    await add_log(transaction_type, from_id, amount, to_id)
    await add_transaction(transaction_type, from_id, amount, to_id)
    
    print(f"💸 Transfer: {from_id} -> {to_id}: {amount:,} VNĐ")
    return True

async def add_money(user_id: str, amount: int, admin_id: str = "system") -> bool:
    """Add money directly"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"❌ User {user_id} not found")
        return False
    
    user_data = user_doc.to_dict()
    user_data["balance"] = user_data.get("balance", 0) + amount
    user_ref.set(user_data)
    
    await add_log("addmoney", user_id, amount, admin_id)
    await add_transaction("addmoney", user_id, amount, admin_id)
    
    print(f"💰 Added {amount:,} to {user_id}, balance: {user_data['balance']:,}")
    return True

async def remove_money(user_id: str, amount: int, admin_id: str = "system") -> bool:
    """Remove money directly"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"❌ User {user_id} not found")
        return False
    
    user_data = user_doc.to_dict()
    if user_data.get("balance", 0) < amount:
        print(f"❌ Insufficient balance: {user_data.get('balance', 0)} < {amount}")
        return False
    
    user_data["balance"] = user_data["balance"] - amount
    user_ref.set(user_data)
    
    await add_log("trutien", user_id, amount, admin_id)
    await add_transaction("trutien", user_id, amount, admin_id)
    
    print(f"💸 Removed {amount:,} from {user_id}, balance: {user_data['balance']:,}")
    return True

async def deduct_bet(user_id: str, amount: int) -> bool:
    """Deduct bet amount directly"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"❌ User {user_id} not found")
        return False
    
    user_data = user_doc.to_dict()
    if user_data.get("balance", 0) < amount:
        print(f"❌ Insufficient balance: {user_data.get('balance', 0)} < {amount}")
        return False
    
    user_data["balance"] = user_data["balance"] - amount
    user_ref.set(user_data)
    print(f"🎲 Deducted bet {amount:,} from {user_id}, balance: {user_data['balance']:,}")
    return True

async def add_win(user_id: str, amount: int) -> bool:
    """Add win amount directly"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"❌ User {user_id} not found")
        return False
    
    user_data = user_doc.to_dict()
    user_data["balance"] = user_data.get("balance", 0) + amount
    user_ref.set(user_data)
    print(f"🎉 Added win {amount:,} to {user_id}, balance: {user_data['balance']:,}")
    return True

async def check_and_deduct_shield(user_id: str) -> bool:
    """Check and deduct free bet shield"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    if user_data.get("freeBetShield", 0) > 0:
        user_data["freeBetShield"] -= 1
        user_ref.set(user_data)
        print(f"🛡️ Shield used for {user_id}, remaining: {user_data['freeBetShield']}")
        return True
    return False

async def check_and_deduct_coupon(user_id: str) -> bool:
    """Check and deduct discount coupon"""
    user_ref = get_user_ref(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    if user_data.get("discountCouponUses", 0) > 0:
        user_data["discountCouponUses"] -= 1
        user_ref.set(user_data)
        print(f"📄 Coupon used for {user_id}, remaining: {user_data['discountCouponUses']}")
        return True
    return False

# ============================================
# CAU CHART GENERATOR
# ============================================
def generate_cau_chart(game_list: List[Dict]) -> BytesIO:
    """Generate professional Tai Xiu statistics chart"""
    
    if not game_list:
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor='#1a0a2e')
        ax.set_facecolor('#1a0a2e')
        ax.text(0.5, 0.5, 'Chưa có dữ liệu phiên nào!\nHãy chơi Tài Xỉu trước.', 
                ha='center', va='center', fontsize=24, color='white', transform=ax.transAxes)
        ax.axis('off')
        buf = BytesIO()
        fig.savefig(buf, format='png', facecolor='#1a0a2e', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf
    
    # Reverse to show oldest first
    game_list = list(reversed(game_list))
    
    results = [g.get('result', 0) for g in game_list]
    dice1_list = [g.get('dice1', 0) for g in game_list]
    dice2_list = [g.get('dice2', 0) for g in game_list]
    dice3_list = [g.get('dice3', 0) for g in game_list]
    tai_xiu_list = [g.get('taiOrXiu', '') for g in game_list]
    
    sessions = list(range(1, len(results) + 1))
    total_phiens = len(results)
    
    # Colors
    bg_dark = '#0d0520'
    tai_color = '#FF4444'
    xiu_color = '#4488FF'
    gold = '#FFD700'
    cyan = '#00FFFF'
    yellow = '#FFFF00'
    white = '#FFFFFF'
    
    # Create figure
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=bg_dark)
    
    # Add gradient background
    gradient = np.linspace(0, 1, 256).reshape(256, 1)
    gradient = np.hstack([gradient, gradient, gradient])
    
    # Create custom layout
    gs = fig.add_gridspec(4, 4, hspace=0.4, wspace=0.3, 
                          top=0.93, bottom=0.05, left=0.05, right=0.98)
    
    # Title
    fig.suptitle('🎲 THỐNG KÊ TÀI XỈU', fontsize=20, fontweight='bold', 
                 color=gold, y=0.98, fontfamily='monospace')
    
    # ==========================================
    # PANEL 1: Current Session Info (Top Right)
    # ==========================================
    ax_info = fig.add_subplot(gs[0, 3])
    ax_info.set_facecolor('#150830')
    ax_info.axis('off')
    
    if total_phiens > 0:
        last_result = results[-1]
        last_tai_xiu = tai_xiu_list[-1]
        last_dice = f"{dice1_list[-1]}-{dice2_list[-1]}-{dice3_list[-1]}"
        
        color = tai_color if last_tai_xiu == 'tai' else xiu_color if last_tai_xiu == 'xiu' else gold
        label = 'TÀI' if last_tai_xiu == 'tai' else 'XỈU' if last_tai_xiu == 'xiu' else 'BỘ BA'
        
        ax_info.text(0.5, 0.85, f'Phiên #{total_phiens}', ha='center', fontsize=13, 
                    color=white, fontweight='bold', fontfamily='monospace')
        ax_info.text(0.5, 0.5, label, ha='center', fontsize=28, color=color, 
                    fontweight='bold', fontfamily='monospace')
        ax_info.text(0.5, 0.2, f'({last_dice})', ha='center', fontsize=11, color='#aaaaaa', 
                    fontfamily='monospace')
    
    # Add border
    for spine in ax_info.spines.values():
        spine.set_edgecolor('#3a2a5e')
        spine.set_linewidth(2)
    
    # ==========================================
    # PANEL 2: Total Score Line Chart
    # ==========================================
    ax1 = fig.add_subplot(gs[0:2, 0:3])
    ax1.set_facecolor('#150830')
    
    ax1.plot(sessions, results, color=white, linewidth=2.5, marker='o', 
             markersize=9, markerfacecolor=gold, markeredgecolor=white,
             markeredgewidth=1.5, zorder=5)
    
    ax1.fill_between(sessions, results, 3, alpha=0.15, color=gold)
    
    # Add value labels
    for i, val in enumerate(results):
        ax1.annotate(str(val), (sessions[i], val), textcoords="offset points", 
                    xytext=(0, 12), ha='center', fontsize=8, color=white, 
                    fontweight='bold', fontfamily='monospace')
    
    ax1.set_ylim(2, 19)
    ax1.set_yticks(range(3, 19))
    ax1.set_ylabel('Tổng Điểm', color=white, fontsize=10, fontfamily='monospace')
    ax1.set_xlabel('Phiên', color=white, fontsize=10, fontfamily='monospace')
    ax1.tick_params(colors=white, labelsize=8)
    ax1.grid(True, alpha=0.2, linestyle='--', color='white')
    ax1.set_title('📊 BIỂU ĐỒ TỔNG ĐIỂM', color=gold, fontsize=11, fontweight='bold', 
                  fontfamily='monospace', pad=8)
    
    for spine in ax1.spines.values():
        spine.set_edgecolor('#3a2a5e')
        spine.set_linewidth(1)
    
    # ==========================================
    # PANEL 3: Dice Charts
    # ==========================================
    ax2 = fig.add_subplot(gs[2, 0:2])
    ax2.set_facecolor('#150830')
    
    ax2.plot(sessions, dice1_list, color='#FF6B6B', linewidth=1.8, marker='s', 
             markersize=6, markerfacecolor='#FF6B6B', label='Xúc xắc 1')
    ax2.plot(sessions, dice2_list, color=cyan, linewidth=1.8, marker='^', 
             markersize=6, markerfacecolor=cyan, label='Xúc xắc 2')
    ax2.plot(sessions, dice3_list, color=yellow, linewidth=1.8, marker='D', 
             markersize=6, markerfacecolor=yellow, label='Xúc xắc 3')
    
    ax2.set_ylim(0.5, 6.5)
    ax2.set_yticks(range(1, 7))
    ax2.set_ylabel('Giá trị', color=white, fontsize=9, fontfamily='monospace')
    ax2.tick_params(colors=white, labelsize=8)
    ax2.grid(True, alpha=0.2, linestyle='--', color='white')
    ax2.legend(loc='upper left', fontsize=8, facecolor='#150830', 
               edgecolor='#3a2a5e', labelcolor=white)
    ax2.set_title('🎲 THỐNG KÊ XÚC XẮC', color=gold, fontsize=11, fontweight='bold', 
                  fontfamily='monospace', pad=8)
    
    for spine in ax2.spines.values():
        spine.set_edgecolor('#3a2a5e')
        spine.set_linewidth(1)
    
    # ==========================================
    # PANEL 4: Cau Display
    # ==========================================
    ax3 = fig.add_subplot(gs[2, 2:])
    ax3.set_facecolor('#150830')
    ax3.axis('off')
    
    # Display Tai/Xiu sequence
    ax3.text(0.5, 0.85, '📈 THỐNG KÊ CẦU', ha='center', fontsize=11, color=gold, 
             fontweight='bold', fontfamily='monospace')
    
    # Draw circles for each result
    n = len(tai_xiu_list)
    max_per_row = 10
    rows = (n + max_per_row - 1) // max_per_row
    
    y_start = 0.6
    y_spacing = 0.15
    
    for row in range(rows):
        start_idx = row * max_per_row
        end_idx = min((row + 1) * max_per_row, n)
        row_count = end_idx - start_idx
        
        x_spacing = 0.9 / row_count
        y_pos = y_start - row * y_spacing
        
        for i, idx in enumerate(range(start_idx, end_idx)):
            x_pos = 0.1 + i * x_spacing + x_spacing / 2
            
            result_type = tai_xiu_list[idx]
            if result_type == 'tai':
                color = tai_color
            elif result_type == 'xiu':
                color = xiu_color
            else:
                color = gold
            
            circle = plt.Circle((x_pos, y_pos), 0.025, color=color, transform=ax3.transAxes)
            ax3.add_patch(circle)
    
    # Legend
    tai_patch = mpatches.Patch(color=tai_color, label='TÀI')
    xiu_patch = mpatches.Patch(color=xiu_color, label='XỈU')
    ax3.legend(handles=[tai_patch, xiu_patch], loc='lower center', fontsize=8, 
               facecolor='#150830', edgecolor='#3a2a5e', labelcolor=white, ncol=2)
    
    # ==========================================
    # PANEL 5: Analysis & Prediction
    # ==========================================
    ax4 = fig.add_subplot(gs[3, :])
    ax4.set_facecolor('#150830')
    ax4.axis('off')
    
    # Calculate stats
    tai_count = sum(1 for t in tai_xiu_list if t == 'tai')
    xiu_count = sum(1 for t in tai_xiu_list if t == 'xiu')
    
    # Current streak
    current_streak = 0
    streak_type = None
    for t in reversed(tai_xiu_list):
        if t == 'triple':
            continue
        if streak_type is None:
            streak_type = t
            current_streak = 1
        elif t == streak_type:
            current_streak += 1
        else:
            break
    
    # Predict
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
    
    # Display
    ax4.text(0.03, 0.85, '📊 PHÂN TÍCH & DỰ ĐOÁN', color=gold, fontsize=13, 
             fontweight='bold', fontfamily='monospace')
    
    ax4.text(0.03, 0.6, f'Tài: {tai_count}/{total_phiens} ({tai_count/total_phiens*100:.0f}%)', 
             color=white, fontsize=10, fontfamily='monospace')
    ax4.text(0.03, 0.4, f'Xỉu: {xiu_count}/{total_phiens} ({xiu_count/total_phiens*100:.0f}%)', 
             color=white, fontsize=10, fontfamily='monospace')
    
    streak_text = f'{current_streak} phiên {streak_type} liên tiếp' if streak_type else 'N/A'
    ax4.text(0.03, 0.2, f'🔥 Chuỗi: {streak_text}', color=white, fontsize=10, 
             fontfamily='monospace')
    
    ax4.text(0.55, 0.6, f'🤖 Dự đoán: {prediction}', color=gold, fontsize=14, 
             fontweight='bold', fontfamily='monospace')
    ax4.text(0.55, 0.35, f'Độ tin cậy: {confidence}%', color='#aaaaaa', fontsize=11, 
             fontfamily='monospace')
    ax4.text(0.55, 0.15, f'Tỷ lệ đúng: 50-65%', color='#777777', fontsize=8, 
             fontfamily='monospace')
    
    # Save to buffer
    buf = BytesIO()
    fig.savefig(buf, format='png', facecolor=bg_dark, bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    return buf

# ============================================
# BOT EVENTS
# ============================================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name} ({bot.user.id})")
    print(f"📡 Connected to {len(bot.guilds)} guilds")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} command(s)")
        for cmd in synced:
            print(f"   📌 /{cmd.name} - {cmd.description}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(bot.guilds)} servers | /help"))

# ============================================
# COOLDOWN CHECK
# ============================================
def check_cooldown(command_name: str, cooldown_seconds: int):
    async def predicate(interaction: discord.Interaction) -> bool:
        user_id = str(interaction.user.id)
        is_on_cooldown, remaining = cooldown_manager.check_cooldown(user_id, command_name, cooldown_seconds)
        
        if is_on_cooldown:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            time_str = ""
            if hours > 0:
                time_str += f"{hours} giờ "
            if minutes > 0:
                time_str += f"{minutes} phút "
            if seconds > 0:
                time_str += f"{seconds} giây"
            await interaction.response.send_message(f"⏰ Vui lòng đợi {time_str.strip()} để sử dụng lệnh này!", ephemeral=True)
            return False
        
        has_overdue, _ = await check_loans_overdue(user_id)
        if has_overdue:
            await interaction.response.send_message("⚠️ Bạn có khoản nợ quá hạn! Hãy trả nợ trước khi sử dụng lệnh này.\nDùng `/nolist` để xem danh sách nợ.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# ============================================
# ECONOMY COMMANDS
# ============================================
@bot.tree.command(name="sodu", description="💰 Xem số dư của bạn")
@check_cooldown("sodu", COOLDOWN_NORMAL)
async def sodu(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = await create_user_if_not_exists(user_id)
    
    embed = create_embed(
        title="💰 Thông Tin Tài Khoản",
        color=COLOR_GOLD,
        fields=[
            ("💵 Số dư hiện tại", f"{user_data['balance']:,} VNĐ", False),
            ("📈 Tổng thắng", f"{user_data.get('totalMoneyWon', 0):,} VNĐ", True),
            ("📉 Tổng thua", f"{user_data.get('totalMoneyLost', 0):,} VNĐ", True),
            ("📅 Ngày tạo", user_data.get('createdAt').strftime("%d/%m/%Y") if user_data.get('createdAt') else "N/A", False)
        ],
        thumbnail_url=interaction.user.display_avatar.url,
        footer_text=f"Người chơi: {interaction.user.name}"
    )
    
    cooldown_manager.set_cooldown(user_id, "sodu")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="daily", description="🎁 Nhận thưởng hàng ngày (100,000 VNĐ)")
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
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await interaction.response.send_message(f"⏰ Bạn đã nhận daily rồi! Vui lòng đợi {hours} giờ {minutes} phút.", ephemeral=True)
                return
    
    success = await add_money(user_id, DAILY_REWARD)
    if success:
        get_user_ref(user_id).update({"dailyLastClaim": datetime.now(timezone.utc)})
        embed = create_embed(title="🎁 Điểm Danh Hàng Ngày", description=f"Bạn đã nhận được **{DAILY_REWARD:,} VNĐ**!", color=COLOR_GOLD, thumbnail_url=interaction.user.display_avatar.url, footer_text="Hẹn gặp lại vào ngày mai!")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Có lỗi xảy ra, vui lòng thử lại!", ephemeral=True)

@bot.tree.command(name="bank", description="🏦 Chuyển tiền cho người chơi khác")
@app_commands.describe(user="Người nhận tiền", amount="Số tiền muốn chuyển (nhập 'all' để chuyển tất cả)")
@check_cooldown("bank", COOLDOWN_NORMAL)
async def bank(interaction: discord.Interaction, user: discord.User, amount: str):
    if user.bot:
        await interaction.response.send_message("❌ Không thể chuyển tiền cho bot!", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Không thể chuyển tiền cho chính mình!", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    target_id = str(user.id)
    sender_data = await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(target_id)
    
    if amount.lower() == "all":
        transfer_amount = sender_data["balance"]
    else:
        try:
            transfer_amount = int(amount)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền không hợp lệ!", ephemeral=True)
            return
    
    if transfer_amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    if transfer_amount > sender_data["balance"]:
        await interaction.response.send_message("❌ Số dư không đủ!", ephemeral=True)
        return
    
    success = await transfer_money(user_id, target_id, transfer_amount)
    if success:
        embed = create_embed(title="🏦 Chuyển Tiền Thành Công", description=f"{EMOJI_MONEY_BAG} **{interaction.user.name}** đã chuyển **{transfer_amount:,} VNĐ** cho **{user.name}**", color=COLOR_SUCCESS, thumbnail_url=user.display_avatar.url, footer_text="Giao dịch đã được ghi nhận")
        cooldown_manager.set_cooldown(user_id, "bank")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Chuyển tiền thất bại!", ephemeral=True)

@bot.tree.command(name="top", description="🏆 Xem bảng xếp hạng")
@check_cooldown("top", COOLDOWN_NORMAL)
async def top(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "top")
    
    class TopSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="💰 Giàu nhất", description="Xếp hạng theo số dư", emoji="💰"),
                discord.SelectOption(label="🏆 Thắng nhiều nhất", description="Xếp hạng theo tổng thắng", emoji="🏆"),
                discord.SelectOption(label="🔥 Chuỗi thắng cao nhất", description="Xếp hạng theo best win streak", emoji="🔥"),
                discord.SelectOption(label="🎮 Chơi nhiều nhất", description="Xếp hạng theo tổng game đã chơi", emoji="🎮")
            ]
            super().__init__(placeholder="Chọn bảng xếp hạng...", options=options)
        
        async def callback(self, select_interaction: discord.Interaction):
            if select_interaction.user.id != interaction.user.id:
                await select_interaction.response.send_message("❌ Đây không phải bảng xếp hạng của bạn!", ephemeral=True)
                return
            selected = self.values[0]
            await select_interaction.response.defer()
            
            users = db.collection("users").get()
            user_list = [doc.to_dict() for doc in users]
            
            if "Giàu nhất" in selected:
                sorted_users = sorted(user_list, key=lambda x: x.get("balance", 0), reverse=True)
                title = "💰 Bảng Xếp Hạng Giàu Nhất"
                field_key = "balance"
                is_money = True
            elif "Thắng nhiều nhất" in selected:
                sorted_users = sorted(user_list, key=lambda x: x.get("totalMoneyWon", 0), reverse=True)
                title = "🏆 Bảng Xếp Hạng Thắng Nhiều Nhất"
                field_key = "totalMoneyWon"
                is_money = True
            elif "Chuỗi thắng" in selected:
                sorted_users = sorted(user_list, key=lambda x: x.get("bestWinStreak", 0), reverse=True)
                title = "🔥 Bảng Xếp Hạng Chuỗi Thắng"
                field_key = "bestWinStreak"
                is_money = False
            else:
                sorted_users = sorted(user_list, key=lambda x: x.get("totalGames", 0), reverse=True)
                title = "🎮 Bảng Xếp Hạng Chơi Nhiều Nhất"
                field_key = "totalGames"
                is_money = False
            
            description = ""
            for i, user_data in enumerate(sorted_users[:10]):
                try:
                    member = interaction.guild.get_member(int(user_data["userId"]))
                    name = member.name if member else user_data["userId"]
                except:
                    name = user_data["userId"]
                value = user_data.get(field_key, 0)
                value_str = f"{value:,} VNĐ" if is_money else f"{value}"
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                description += f"{medal} **{name}** - {value_str}\n"
            
            embed = create_embed(title=title, description=description, color=COLOR_GOLD, footer_text="Top 10 người chơi")
            await select_interaction.message.edit(embed=embed, view=self.view)
    
    class TopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.add_item(TopSelect())
    
    users = db.collection("users").get()
    user_list = [doc.to_dict() for doc in users]
    sorted_users = sorted(user_list, key=lambda x: x.get("balance", 0), reverse=True)
    
    description = ""
    for i, user_data in enumerate(sorted_users[:10]):
        try:
            member = interaction.guild.get_member(int(user_data["userId"]))
            name = member.name if member else user_data["userId"]
        except:
            name = user_data["userId"]
        value = user_data.get("balance", 0)
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        description += f"{medal} **{name}** - {value:,} VNĐ\n"
    
    embed = create_embed(title="💰 Bảng Xếp Hạng Giàu Nhất", description=description, color=COLOR_GOLD, footer_text="Sử dụng menu bên dưới để thay đổi bảng xếp hạng")
    await interaction.response.send_message(embed=embed, view=TopView(), ephemeral=True)

@bot.tree.command(name="info", description="📊 Xem thông tin người chơi")
@app_commands.describe(user="Người chơi muốn xem (bỏ trống để xem bản thân)")
@check_cooldown("info", COOLDOWN_NORMAL)
async def info(interaction: discord.Interaction, user: Optional[discord.User] = None):
    target = user or interaction.user
    target_id = str(target.id)
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "info")
    
    user_data = await create_user_if_not_exists(target_id)
    profile_color_name = user_data.get("profileColor", "🔵 Xanh dương")
    profile_color = PROFILE_COLORS.get(profile_color_name, COLOR_BLUE)
    
    badges = []
    if user_data.get("balance", 0) >= BADGE_TY_PHU:
        badges.append(f"{EMOJI_CROWN} Tỷ Phú")
    elif user_data.get("balance", 0) >= BADGE_DAI_GIA:
        badges.append(f"{EMOJI_GEM} Đại Gia")
    elif user_data.get("balance", 0) >= BADGE_TRIEU_PHU:
        badges.append(f"{EMOJI_COIN} Triệu Phú")
    if user_data.get("totalGames", 0) >= BADGE_CAO_THU:
        badges.append(f"{EMOJI_DICE} Cao Thủ Tài Xỉu")
    if user_data.get("bestWinStreak", 0) >= BADGE_STREAK_GOD:
        badges.append(f"{EMOJI_FIRE} Chuỗi Thắng Thần Thánh")
    badges_str = "\n".join(badges) if badges else "Chưa có huy hiệu"
    
    loans_ref = db.collection("loans")
    borrowing = loans_ref.where(filter=FieldFilter("borrowerId", "==", target_id)).where(filter=FieldFilter("repaid", "==", False)).get()
    lending = loans_ref.where(filter=FieldFilter("lenderId", "==", target_id)).where(filter=FieldFilter("repaid", "==", False)).get()
    total_borrowing = sum(loan.to_dict().get("amount", 0) for loan in borrowing)
    total_lending = sum(loan.to_dict().get("amount", 0) for loan in lending)
    
    embed = create_embed(
        title="📊 Thông Tin Người Chơi",
        description=f"### 👤 {target.name}",
        color=profile_color,
        fields=[
            ("", "**━━━ 📊 THỐNG KÊ ━━━**", False),
            ("🎮 Tổng ván chơi", f"{user_data.get('totalGames', 0)}", True),
            ("📈 Tổng thắng", f"{user_data.get('totalWins', 0)}", True),
            ("📉 Tổng thua", f"{user_data.get('totalLosses', 0)}", True),
            ("🔥 Chuỗi thắng hiện tại", f"{user_data.get('currentWinStreak', 0)}", True),
            ("❄️ Chuỗi thua hiện tại", f"{user_data.get('currentLoseStreak', 0)}", True),
            ("🏆 Chuỗi thắng cao nhất", f"{user_data.get('bestWinStreak', 0)}", True),
            ("📅 Ngày tham gia", user_data.get('createdAt').strftime("%d/%m/%Y") if user_data.get('createdAt') else "N/A", True),
            ("", "**━━━ 💳 TÀI CHÍNH ━━━**", False),
            ("💵 Số dư hiện tại", f"{user_data.get('balance', 0):,} VNĐ", True),
            ("🏆 Tổng tiền thắng", f"{user_data.get('totalMoneyWon', 0):,} VNĐ", True),
            ("💸 Tổng tiền thua", f"{user_data.get('totalMoneyLost', 0):,} VNĐ", True),
            ("💰 Đang nợ", f"{total_borrowing:,} VNĐ", True),
            ("💳 Đã cho vay", f"{total_lending:,} VNĐ", True),
            ("", "**━━━ 🏅 HUY HIỆU ━━━**", False),
            ("Danh sách huy hiệu", badges_str, False),
        ],
        thumbnail_url=target.display_avatar.url,
        footer_text=f"ID: {target_id}"
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="🏅 Xem hạng của bạn")
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
            if str(u.get("userId")) == user_id:
                return i + 1, len(user_list)
        return len(user_list), len(user_list)
    
    balance_rank, total = get_rank("balance")
    games_rank, _ = get_rank("totalGames")
    streak_rank, _ = get_rank("bestWinStreak")
    wins_rank, _ = get_rank("totalMoneyWon")
    
    embed = create_embed(
        title="🏅 Bảng Xếp Hạng Của Bạn",
        color=COLOR_GOLD,
        fields=[
            ("🏆 Hạng giàu", f"#{balance_rank}/{total}", True),
            ("🎮 Hạng game", f"#{games_rank}/{total}", True),
            ("🔥 Hạng chuỗi thắng", f"#{streak_rank}/{total}", True),
            ("📈 Hạng thắng", f"#{wins_rank}/{total}", True),
        ],
        thumbnail_url=interaction.user.display_avatar.url,
        footer_text=f"Tổng người chơi: {total}"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="profilecolor", description="🎨 Đổi màu profile")
@check_cooldown("profilecolor", COOLDOWN_NORMAL)
async def profilecolor(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "profilecolor")
    
    class ColorSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Đỏ", description="Màu đỏ", emoji="🔴"),
                discord.SelectOption(label="Xanh lá", description="Màu xanh lá", emoji="🟢"),
                discord.SelectOption(label="Xanh dương", description="Màu xanh dương", emoji="🔵"),
                discord.SelectOption(label="Tím", description="Màu tím", emoji="🟣"),
                discord.SelectOption(label="Vàng", description="Màu vàng", emoji="🟡"),
                discord.SelectOption(label="Đen", description="Màu đen", emoji="⚫")
            ]
            super().__init__(placeholder="Chọn màu profile...", options=options)
        
        async def callback(self, select_interaction: discord.Interaction):
            if select_interaction.user.id != interaction.user.id:
                await select_interaction.response.send_message("❌ Đây không phải menu của bạn!", ephemeral=True)
                return
            selected = self.values[0]
            option_labels = {o.label: o for o in self.options}
            option = option_labels[selected]
            color_name = f"{option.emoji} {option.label}"
            
            get_user_ref(str(select_interaction.user.id)).update({"profileColor": color_name})
            embed = create_embed(title="🎨 Đổi Màu Profile", description=f"Đã đổi màu profile thành **{color_name}**", color=PROFILE_COLORS.get(color_name, COLOR_BLUE), thumbnail_url=select_interaction.user.display_avatar.url, footer_text="Màu sẽ hiển thị trong /info")
            await select_interaction.response.send_message(embed=embed, ephemeral=True)
    
    class ColorView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.add_item(ColorSelect())
    
    embed = create_embed(title="🎨 Chọn Màu Profile", description="Chọn màu sắc cho profile của bạn từ menu bên dưới", color=COLOR_INFO)
    await interaction.response.send_message(embed=embed, view=ColorView(), ephemeral=True)

# ============================================
# SHOP COMMAND
# ============================================
@bot.tree.command(name="shop", description="🛒 Mở cửa hàng vật phẩm")
@check_cooldown("shop", COOLDOWN_NORMAL)
async def shop(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "shop")
    
    class ShopButton(discord.ui.Button):
        def __init__(self, label: str, item_name: str, price: int, description: str, emoji: str):
            super().__init__(label=label, style=discord.ButtonStyle.primary, emoji=emoji)
            self.item_name = item_name
            self.price = price
            self.description = description
        
        async def callback(self, button_interaction: discord.Interaction):
            if button_interaction.user.id != interaction.user.id:
                await button_interaction.response.send_message("❌ Đây không phải shop của bạn!", ephemeral=True)
                return
            
            user_id_btn = str(button_interaction.user.id)
            user_ref = get_user_ref(user_id_btn)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                await button_interaction.response.send_message("❌ Người dùng không tồn tại!", ephemeral=True)
                return
            
            user_data_btn = user_doc.to_dict()
            
            if user_data_btn["balance"] < self.price:
                await button_interaction.response.send_message(f"❌ Số dư không đủ! Cần {self.price:,} VNĐ", ephemeral=True)
                return
            
            user_data_btn["balance"] -= self.price
            
            if "Phiếu Giảm Giá" in self.item_name:
                user_data_btn["discountCouponUses"] = user_data_btn.get("discountCouponUses", 0) + 3
                msg = f"✅ Mua thành công **{self.item_name}**! Bạn có thêm 3 lượt sử dụng."
            else:
                user_data_btn["freeBetShield"] = user_data_btn.get("freeBetShield", 0) + 1
                msg = f"✅ Mua thành công **{self.item_name}**! Khi thua sẽ không mất tiền."
            
            user_ref.set(user_data_btn)
            await add_log("shop", user_id_btn, self.price, description=self.item_name)
            await add_transaction("shop", user_id_btn, -self.price, description=self.item_name)
            await button_interaction.response.send_message(msg, ephemeral=True)
    
    class ShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.add_item(ShopButton("Mua", "📄 Phiếu Giảm Giá", 100000, "Giảm 50,000 VNĐ khi chơi lỗ đít (3 lượt)", "📄"))
            self.add_item(ShopButton("Mua", "🛡️ Phiếu Miễn Tiền Cược", 500000, "Thua không mất tiền (1 lượt)", "🛡️"))
    
    embed = create_embed(
        title="🛒 Cửa Hàng Vật Phẩm",
        description="Chọn vật phẩm bạn muốn mua:",
        color=COLOR_GOLD,
        fields=[
            ("📄 Phiếu Giảm Giá", "💰 Giá: **100,000 VNĐ**\n📝 Công dụng: Giảm 50,000 VNĐ khi chơi lỗ đít\n🔢 3 lượt sử dụng", False),
            ("🛡️ Phiếu Miễn Tiền Cược", "💰 Giá: **500,000 VNĐ**\n📝 Công dụng: Nếu thua sẽ không mất tiền\n🎯 Áp dụng: Tài Xỉu, CoinFlip, Slot", False),
        ],
        footer_text="Nhấn nút bên dưới để mua"
    )
    await interaction.response.send_message(embed=embed, view=ShopView(), ephemeral=True)

# ============================================
# LOAN COMMANDS
# ============================================
@bot.tree.command(name="vay", description="💳 Vay tiền từ người chơi khác")
@app_commands.describe(user="Người cho vay", amount="Số tiền muốn vay")
@check_cooldown("vay", COOLDOWN_NORMAL)
async def vay(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.bot:
        await interaction.response.send_message("❌ Không thể vay bot!", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Không thể tự vay chính mình!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    target_id = str(user.id)
    await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(target_id)
    
    lender_data = await get_user_data(target_id)
    if lender_data["balance"] < amount:
        await interaction.response.send_message(f"❌ {user.name} không đủ tiền để cho vay!", ephemeral=True)
        return
    
    class LoanView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
        
        @discord.ui.button(label="Đồng Ý", style=discord.ButtonStyle.success, emoji="✅")
        async def accept(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("❌ Chỉ người được tag mới có quyền đồng ý!", ephemeral=True)
                return
            
            await button_interaction.response.defer()
            
            now = datetime.now(timezone.utc)
            due_at = now + timedelta(days=LOAN_DUE_DAYS)
            
            success = await transfer_money(target_id, user_id, amount, "loan")
            
            if success:
                loan_ref = db.collection("loans").add({
                    "borrowerId": user_id,
                    "lenderId": target_id,
                    "amount": amount,
                    "createdAt": now,
                    "dueAt": due_at,
                    "repaid": False
                })
                loan_id = loan_ref[1].id
                
                embed = create_embed(
                    title="✅ Vay Tiền Thành Công",
                    description=f"**{interaction.user.name}** đã vay **{amount:,} VNĐ** từ **{user.name}**",
                    color=COLOR_SUCCESS,
                    fields=[
                        ("📋 Mã khoản vay", loan_id, False),
                        ("📅 Hạn trả", due_at.strftime("%d/%m/%Y"), False),
                        ("⚠️ Lưu ý", "Quá hạn sẽ bị khóa game!", False)
                    ],
                    footer_text=f"Dùng /tra {loan_id} để trả nợ"
                )
                await button_interaction.message.edit(embed=embed, view=None)
            else:
                await button_interaction.message.edit(content="❌ Có lỗi xảy ra!", view=None)
        
        @discord.ui.button(label="Từ Chối", style=discord.ButtonStyle.danger, emoji="❌")
        async def reject(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("❌ Chỉ người được tag mới có quyền từ chối!", ephemeral=True)
                return
            
            embed = create_embed(title="❌ Từ Chối Vay", description=f"**{user.name}** đã từ chối cho **{interaction.user.name}** vay tiền.", color=COLOR_ERROR)
            await button_interaction.message.edit(embed=embed, view=None)
    
    embed = create_embed(
        title="💳 Yêu Cầu Vay Tiền",
        description=f"**{interaction.user.name}** muốn vay **{amount:,} VNĐ** từ **{user.name}**",
        color=COLOR_WARNING,
        fields=[("⏰ Hết hạn", "60 giây", False)],
        thumbnail_url=interaction.user.display_avatar.url,
        footer_text=f"Người cho vay: {user.name}"
    )
    
    cooldown_manager.set_cooldown(user_id, "vay")
    await interaction.response.send_message(embed=embed, view=LoanView())

@bot.tree.command(name="tra", description="💳 Trả nợ")
@app_commands.describe(loan_id="Mã khoản vay")
@check_cooldown("tra", COOLDOWN_NORMAL)
async def tra(interaction: discord.Interaction, loan_id: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "tra")
    
    loan_doc = get_loan_ref(loan_id).get()
    if not loan_doc.exists:
        await interaction.response.send_message("❌ Khoản vay không tồn tại!", ephemeral=True)
        return
    
    loan_data = loan_doc.to_dict()
    
    if loan_data["repaid"]:
        await interaction.response.send_message("❌ Khoản vay này đã được trả!", ephemeral=True)
        return
    
    if loan_data["borrowerId"] != user_id:
        await interaction.response.send_message("❌ Đây không phải khoản vay của bạn!", ephemeral=True)
        return
    
    user_data = await get_user_data(user_id)
    if user_data["balance"] < loan_data["amount"]:
        await interaction.response.send_message(f"❌ Số dư không đủ! Cần {loan_data['amount']:,} VNĐ", ephemeral=True)
        return
    
    success = await transfer_money(user_id, loan_data["lenderId"], loan_data["amount"], "repay")
    
    if success:
        get_loan_ref(loan_id).update({"repaid": True})
        embed = create_embed(
            title="✅ Trả Nợ Thành Công",
            description=f"Đã trả **{loan_data['amount']:,} VNĐ** cho người cho vay!",
            color=COLOR_SUCCESS,
            fields=[("📋 Mã khoản vay", loan_id, False)],
            thumbnail_url=interaction.user.display_avatar.url
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Trả nợ thất bại!", ephemeral=True)

@bot.tree.command(name="nolist", description="📋 Xem danh sách nợ")
@check_cooldown("nolist", COOLDOWN_NORMAL)
async def nolist(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "nolist")
    
    loans_as_borrower = db.collection("loans").where(filter=FieldFilter("borrowerId", "==", user_id)).get()
    loans_as_lender = db.collection("loans").where(filter=FieldFilter("lenderId", "==", user_id)).get()
    
    all_loans = list(loans_as_borrower) + list(loans_as_lender)
    
    if not all_loans:
        await interaction.response.send_message("📋 Bạn không có khoản nợ nào!", ephemeral=True)
        return
    
    description = "**Khoản vay của bạn:**\n\n"
    shown_ids = set()
    
    for loan_doc in all_loans:
        loan = loan_doc.to_dict()
        loan_id = loan_doc.id
        
        if loan_id in shown_ids:
            continue
        shown_ids.add(loan_id)
        
        try:
            borrower = interaction.guild.get_member(int(loan["borrowerId"]))
            borrower_name = borrower.name if borrower else loan["borrowerId"]
        except:
            borrower_name = loan["borrowerId"]
        
        try:
            lender = interaction.guild.get_member(int(loan["lenderId"]))
            lender_name = lender.name if lender else loan["lenderId"]
        except:
            lender_name = loan["lenderId"]
        
        status = "✅ Đã trả" if loan["repaid"] else "⚠️ Chưa trả"
        if not loan["repaid"] and isinstance(loan.get("dueAt"), datetime) and loan["dueAt"] < datetime.now(timezone.utc):
            status = "🔴 QUÁ HẠN"
        
        due_at = loan.get("dueAt")
        due_str = due_at.strftime("%d/%m/%Y") if isinstance(due_at, datetime) else "N/A"
        
        description += f"📋 **ID:** `{loan_id}`\n"
        description += f"👤 Người vay: **{borrower_name}**\n"
        description += f"💳 Người cho vay: **{lender_name}**\n"
        description += f"💰 Số tiền: **{loan['amount']:,} VNĐ**\n"
        description += f"📅 Hạn trả: **{due_str}**\n"
        description += f"📊 Trạng thái: {status}\n\n"
    
    embed = create_embed(title="📋 Danh Sách Nợ", description=description, color=COLOR_WARNING, footer_text="Dùng /tra <loan_id> để trả nợ")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="anxin", description="🙏 Xin tiền người chơi khác")
@app_commands.describe(user="Người muốn xin", amount="Số tiền muốn xin")
@check_cooldown("anxin", COOLDOWN_NORMAL)
async def anxin(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.bot:
        await interaction.response.send_message("❌ Không thể xin bot!", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Không thể tự xin chính mình!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    target_id = str(user.id)
    await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(target_id)
    
    target_data = await get_user_data(target_id)
    if target_data["balance"] < amount:
        await interaction.response.send_message(f"❌ {user.name} không đủ tiền để cho!", ephemeral=True)
        return
    
    class XinView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
        
        @discord.ui.button(label="Cho", style=discord.ButtonStyle.success, emoji="✅")
        async def give(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("❌ Chỉ người được tag mới có quyền!", ephemeral=True)
                return
            
            await button_interaction.response.defer()
            success = await transfer_money(target_id, user_id, amount, "anxin")
            
            if success:
                embed = create_embed(title="✅ Xin Tiền Thành Công", description=f"**{user.name}** đã cho **{interaction.user.name}** **{amount:,} VNĐ**!", color=COLOR_SUCCESS, thumbnail_url=interaction.user.display_avatar.url)
                await button_interaction.message.edit(embed=embed, view=None)
            else:
                await button_interaction.message.edit(content="❌ Có lỗi xảy ra!", view=None)
        
        @discord.ui.button(label="Từ Chối", style=discord.ButtonStyle.danger, emoji="❌")
        async def reject(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("❌ Chỉ người được tag mới có quyền!", ephemeral=True)
                return
            
            embed = create_embed(title="❌ Từ Chối", description=f"**{user.name}** đã từ chối cho **{interaction.user.name}** tiền.", color=COLOR_ERROR)
            await button_interaction.message.edit(embed=embed, view=None)
    
    embed = create_embed(
        title="🙏 Xin Tiền",
        description=f"**{interaction.user.name}** muốn xin **{amount:,} VNĐ** từ **{user.name}**",
        color=COLOR_WARNING,
        thumbnail_url=interaction.user.display_avatar.url,
        footer_text=f"Người được xin: {user.name}"
    )
    
    cooldown_manager.set_cooldown(user_id, "anxin")
    await interaction.response.send_message(embed=embed, view=XinView())

# ============================================
# GAME: TAI XIU
# ============================================
@bot.tree.command(name="taixiu", description="🎲 Chơi Tài Xỉu")
@app_commands.describe(cua="Cửa cược (tai/xiu/chan/le hoặc số 3-18)", cuoc="Số tiền cược (nhập 'all' để cược tất cả)")
@check_cooldown("taixiu", COOLDOWN_NORMAL)
async def taixiu(interaction: discord.Interaction, cua: str, cuoc: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "taixiu")
    
    user_data = await create_user_if_not_exists(user_id)
    
    if cuoc.lower() == "all":
        bet_amount = user_data["balance"]
    else:
        try:
            bet_amount = int(cuoc)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền cược không hợp lệ!", ephemeral=True)
            return
    
    if bet_amount <= 0:
        await interaction.response.send_message("❌ Số tiền cược phải lớn hơn 0!", ephemeral=True)
        return
    if bet_amount > user_data["balance"]:
        await interaction.response.send_message("❌ Số dư không đủ!", ephemeral=True)
        return
    
    cua_lower = cua.lower()
    is_specific = False
    specific_number = 0
    
    if cua_lower in ["tai", "tài"]:
        bet_type = "tai"
    elif cua_lower in ["xiu", "xỉu"]:
        bet_type = "xiu"
    elif cua_lower in ["chan", "chẵn"]:
        bet_type = "chan"
    elif cua_lower in ["le", "lẻ"]:
        bet_type = "le"
    else:
        try:
            specific_number = int(cua_lower)
            if 3 <= specific_number <= 18:
                is_specific = True
                bet_type = str(specific_number)
            else:
                await interaction.response.send_message("❌ Cửa cược không hợp lệ! (tai/xiu/chan/le hoặc 3-18)", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Cửa cược không hợp lệ! (tai/xiu/chan/le hoặc 3-18)", ephemeral=True)
            return
    
    success = await deduct_bet(user_id, bet_amount)
    if not success:
        await interaction.response.send_message("❌ Không thể trừ tiền cược!", ephemeral=True)
        return
    
    dice1, dice2, dice3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
    total = dice1 + dice2 + dice3
    
    dice_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}
    
    embed = create_embed(title="🎲 Tài Xỉu", description="Đang lắc xúc xắc...", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    
    for i in range(3):
        await asyncio.sleep(0.8)
        if i == 0:
            desc = f"{dice_emojis[dice1]} ? ?"
        elif i == 1:
            desc = f"{dice_emojis[dice1]} {dice_emojis[dice2]} ?"
        else:
            desc = f"{dice_emojis[dice1]} {dice_emojis[dice2]} {dice_emojis[dice3]}"
        
        embed = create_embed(title="🎲 Tài Xỉu", description=f"**Xúc xắc:** {desc}\n\n🎲 Tổng điểm: **{total}**", color=COLOR_GOLD)
        await msg.edit(embed=embed)
    
    is_tai = 11 <= total <= 17
    is_xiu = 4 <= total <= 10
    is_chan = total % 2 == 0
    is_le = total % 2 == 1
    is_triple = total in [3, 18]
    
    win = False
    multiplier = 0
    
    if is_specific:
        if total == specific_number:
            multiplier = SPECIFIC_NUMBER_PAYOUTS[specific_number]
            win = True
    elif bet_type == "tai":
        if is_tai and not is_triple:
            multiplier = 2
            win = True
    elif bet_type == "xiu":
        if is_xiu and not is_triple:
            multiplier = 2
            win = True
    elif bet_type == "chan":
        if is_chan:
            multiplier = 2
            win = True
    elif bet_type == "le":
        if is_le:
            multiplier = 2
            win = True
    
    if is_triple:
        tai_xiu_text = "⚠️ BỘ BA"
    elif is_tai:
        tai_xiu_text = f"{EMOJI_TAI} TÀI"
    else:
        tai_xiu_text = f"{EMOJI_XIU} XỈU"
    
    chan_le_text = f"{EMOJI_CHAN} CHẴN" if is_chan else f"{EMOJI_LE} LẺ"
    
    if not win:
        has_shield = await check_and_deduct_shield(user_id)
        if has_shield:
            await add_win(user_id, bet_amount)
            result_text = "🛡️ **Phiếu Miễn Cược** đã bảo vệ bạn! Tiền cược được hoàn trả."
            await update_user_stats(user_id, False, bet_amount, 0)
        else:
            result_text = "😢 Bạn đã thua!"
            await update_user_stats(user_id, False, bet_amount, 0)
    else:
        win_amount = bet_amount * multiplier
        await add_win(user_id, win_amount)
        result_text = f"🎉 Bạn đã thắng **{win_amount:,} VNĐ**! (x{multiplier})"
        await update_user_stats(user_id, True, bet_amount, win_amount)
    
    get_game_history_ref().add({
        "result": total,
        "dice1": dice1,
        "dice2": dice2,
        "dice3": dice3,
        "betType": bet_type,
        "betAmount": bet_amount,
        "win": win,
        "multiplier": multiplier,
        "taiOrXiu": "tai" if is_tai else ("xiu" if is_xiu else "triple"),
        "createdAt": datetime.now(timezone.utc),
        "userId": user_id
    })
    
    embed = create_embed(
        title="🎲 Kết Quả Tài Xỉu",
        description=f"**Xúc xắc:** {dice_emojis[dice1]} • {dice_emojis[dice2]} • {dice_emojis[dice3]}\n\n📊 Tổng điểm: **{total}**\n🎯 Kết quả: {tai_xiu_text} | {chan_le_text}\n\n{result_text}",
        color=COLOR_SUCCESS if win else COLOR_ERROR
    )
    await msg.edit(embed=embed)

# ============================================
# GAME: COINFLIP
# ============================================
@bot.tree.command(name="coinflip", description="🪙 Tung đồng xu")
@app_commands.describe(choice="Chọn mặt (head/tail)", amount="Số tiền cược (nhập 'all' để cược tất cả)")
@check_cooldown("coinflip", COOLDOWN_NORMAL)
async def coinflip(interaction: discord.Interaction, choice: str, amount: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "coinflip")
    
    user_data = await create_user_if_not_exists(user_id)
    
    if amount.lower() == "all":
        bet_amount = user_data["balance"]
    else:
        try:
            bet_amount = int(amount)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền không hợp lệ!", ephemeral=True)
            return
    
    if bet_amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    if bet_amount > user_data["balance"]:
        await interaction.response.send_message("❌ Số dư không đủ!", ephemeral=True)
        return
    
    choice_lower = choice.lower()
    if choice_lower in ["mặt sấp"]:
        choice_lower = "tail"
    elif choice_lower in ["mặt ngửa"]:
        choice_lower = "head"
    
    if choice_lower not in ["head", "tail"]:
        await interaction.response.send_message("❌ Chọn head hoặc tail!", ephemeral=True)
        return
    
    success = await deduct_bet(user_id, bet_amount)
    if not success:
        await interaction.response.send_message("❌ Không thể trừ tiền cược!", ephemeral=True)
        return
    
    embed = create_embed(title="🪙 CoinFlip", description="Đang tung đồng xu...", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    
    for _ in range(3):
        await asyncio.sleep(0.5)
        embed = create_embed(title="🪙 CoinFlip", description="🪙 Đang quay...", color=COLOR_GOLD)
        await msg.edit(embed=embed)
    
    result = random.choice(["head", "tail"])
    result_emoji = "🪙 Mặt Ngửa (Head)" if result == "head" else "🪙 Mặt Sấp (Tail)"
    win = choice_lower == result
    
    if win:
        win_amount = bet_amount * 2
        await add_win(user_id, win_amount)
        result_text = f"🎉 Bạn thắng **{win_amount:,} VNĐ**! (x2)"
        await update_user_stats(user_id, True, bet_amount, win_amount)
        color = COLOR_SUCCESS
    else:
        has_shield = await check_and_deduct_shield(user_id)
        if has_shield:
            await add_win(user_id, bet_amount)
            result_text = "🛡️ Phiếu Miễn Cược bảo vệ bạn! Tiền được hoàn trả."
            await update_user_stats(user_id, False, bet_amount, 0)
        else:
            result_text = "😢 Bạn đã thua!"
            await update_user_stats(user_id, False, bet_amount, 0)
        color = COLOR_ERROR
    
    embed = create_embed(title="🪙 Kết Quả CoinFlip", description=f"**Kết quả:** {result_emoji}\n\n{result_text}", color=color)
    await msg.edit(embed=embed)

# ============================================
# GAME: SLOT MACHINE
# ============================================
@bot.tree.command(name="slot", description="🎰 Quay máy đánh bạc")
@app_commands.describe(amount="Số tiền cược (nhập 'all' để cược tất cả)")
@check_cooldown("slot", COOLDOWN_NORMAL)
async def slot(interaction: discord.Interaction, amount: str):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "slot")
    
    user_data = await create_user_if_not_exists(user_id)
    
    if amount.lower() == "all":
        bet_amount = user_data["balance"]
    else:
        try:
            bet_amount = int(amount)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền không hợp lệ!", ephemeral=True)
            return
    
    if bet_amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    if bet_amount > user_data["balance"]:
        await interaction.response.send_message("❌ Số dư không đủ!", ephemeral=True)
        return
    
    success = await deduct_bet(user_id, bet_amount)
    if not success:
        await interaction.response.send_message("❌ Không thể trừ tiền cược!", ephemeral=True)
        return
    
    reels = [[random.choice(SLOT_SYMBOLS) for _ in range(3)] for _ in range(3)]
    
    embed = create_embed(title="🎰 Slot Machine", description="Đang quay...", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    
    for i in range(4):
        await asyncio.sleep(0.6)
        display = ""
        for row in range(3):
            if i < 3:
                temp_row = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
            else:
                temp_row = reels[row]
            display += " ".join(temp_row) + "\n"
        
        embed = create_embed(title="🎰 Slot Machine", description=f"```\n{display}```", color=COLOR_GOLD)
        await msg.edit(embed=embed)
    
    middle_row = reels[1]
    row_str = "".join(middle_row)
    
    win = False
    multiplier = 0
    
    if row_str in SLOT_PAYOUTS:
        multiplier = SLOT_PAYOUTS[row_str]
        win = True
    elif middle_row[0] == middle_row[1] or middle_row[1] == middle_row[2] or middle_row[0] == middle_row[2]:
        multiplier = 1.5
        win = True
    
    if win:
        win_amount = int(bet_amount * multiplier)
        await add_win(user_id, win_amount)
        result_text = f"🎉 Bạn thắng **{win_amount:,} VNĐ**! (x{multiplier})"
        await update_user_stats(user_id, True, bet_amount, win_amount)
        color = COLOR_SUCCESS
    else:
        has_shield = await check_and_deduct_shield(user_id)
        if has_shield:
            await add_win(user_id, bet_amount)
            result_text = "🛡️ Phiếu Miễn Cược bảo vệ bạn! Tiền được hoàn trả."
            await update_user_stats(user_id, False, bet_amount, 0)
        else:
            result_text = "😢 Bạn đã thua!"
            await update_user_stats(user_id, False, bet_amount, 0)
        color = COLOR_ERROR
    
    final_display = ""
    for row in reels:
        final_display += " ".join(row) + "\n"
    
    embed = create_embed(title="🎰 Kết Quả Slot", description=f"```\n{final_display}```\n\n{result_text}", color=color)
    await msg.edit(embed=embed)

# ============================================
# GAME: CHOI LO DIT
# ============================================
@bot.tree.command(name="choilodit", description="🎯 Chơi lỗ đít người khác")
@app_commands.describe(user="Người bị chơi lỗ đít")
@check_cooldown("choilodit", COOLDOWN_NORMAL)
async def choilodit(interaction: discord.Interaction, user: discord.User):
    if user.bot:
        await interaction.response.send_message("❌ Không thể chơi lỗ đít bot!", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Không thể tự chơi chính mình!", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    target_id = str(user.id)
    
    await create_user_if_not_exists(user_id)
    await create_user_if_not_exists(target_id)
    
    has_coupon = await check_and_deduct_coupon(user_id)
    price = 50000 if has_coupon else 100000
    
    user_data = await get_user_data(user_id)
    if user_data["balance"] < price:
        await interaction.response.send_message(f"❌ Số dư không đủ! Cần {price:,} VNĐ", ephemeral=True)
        return
    
    success = await transfer_money(user_id, target_id, price, "lodit")
    
    if success:
        coupon_text = " (đã dùng phiếu giảm giá 50%)" if has_coupon else ""
        embed = create_embed(
            title="🎯 Chơi Lỗ Đít",
            description=f"**{interaction.user.name}** đã chơi lỗ đít của **{user.name}**{coupon_text}\n\n💸 Tiền chuyển: **{price:,} VNĐ**",
            color=COLOR_SUCCESS,
            thumbnail_url=user.display_avatar.url
        )
        cooldown_manager.set_cooldown(user_id, "choilodit")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Có lỗi xảy ra!", ephemeral=True)

# ============================================
# CAU COMMAND
# ============================================
@bot.tree.command(name="cau", description="📊 Xem biểu đồ thống kê cầu Tài Xỉu")
@check_cooldown("cau", COOLDOWN_NORMAL)
async def cau(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "cau")
    
    # Animation
    await interaction.response.send_message("⏳ Đang phân tích cầu...")
    msg = await interaction.original_response()
    await asyncio.sleep(1)
    
    await msg.edit(content="📊 Đang tạo biểu đồ...")
    await asyncio.sleep(1)
    
    await msg.edit(content="🤖 AI đang phân tích...")
    
    # Get game history
    games = get_game_history_ref().order_by("createdAt", direction=firestore.Query.DESCENDING).limit(20).get()
    game_list = [doc.to_dict() for doc in games]
    
    if len(game_list) < 3:
        await msg.edit(content="❌ Cần ít nhất 3 phiên Tài Xỉu để phân tích! Hãy chơi /taixiu trước.")
        return
    
    # Generate chart
    buf = generate_cau_chart(game_list)
    
    # Send image
    await msg.edit(content=None, attachments=[discord.File(buf, filename="cau.png")])

# ============================================
# ADMIN COMMANDS
# ============================================
@bot.tree.command(name="addadmin", description="👑 Thêm admin (Chỉ Super Admin)")
@app_commands.describe(user="Người dùng muốn thêm làm admin")
async def addadmin(interaction: discord.Interaction, user: discord.User):
    if not await is_super_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        return
    
    target_id = str(user.id)
    admin_doc = get_admin_ref(target_id).get()
    
    if admin_doc.exists:
        await interaction.response.send_message(f"❌ {user.name} đã là admin!", ephemeral=True)
        return
    
    get_admin_ref(target_id).set({"userId": target_id, "role": "mini"})
    embed = create_embed(title="👑 Thêm Admin", description=f"Đã thêm **{user.name}** làm **Mini Admin**!", color=COLOR_GOLD, thumbnail_url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="removeadmin", description="👑 Xóa admin (Chỉ Super Admin)")
@app_commands.describe(user="Người dùng muốn xóa khỏi admin")
async def removeadmin(interaction: discord.Interaction, user: discord.User):
    if not await is_super_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        return
    
    target_id = str(user.id)
    admin_doc = get_admin_ref(target_id).get()
    
    if not admin_doc.exists:
        await interaction.response.send_message(f"❌ {user.name} không phải là admin!", ephemeral=True)
        return
    
    get_admin_ref(target_id).delete()
    embed = create_embed(title="👑 Xóa Admin", description=f"Đã xóa **{user.name}** khỏi admin!", color=COLOR_RED, thumbnail_url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addmoney", description="💰 Thêm tiền cho người chơi (Admin)")
@app_commands.describe(user="Người nhận tiền", amount="Số tiền")
async def addmoney(interaction: discord.Interaction, user: discord.User, amount: int):
    if not await is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    
    target_id = str(user.id)
    await create_user_if_not_exists(target_id)
    success = await add_money(target_id, amount, str(interaction.user.id))
    
    if success:
        embed = create_embed(title="💰 Thêm Tiền", description=f"Đã thêm **{amount:,} VNĐ** cho **{user.name}**!", color=COLOR_SUCCESS, thumbnail_url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Có lỗi xảy ra!", ephemeral=True)

@bot.tree.command(name="trutien", description="💸 Trừ tiền người chơi (Admin)")
@app_commands.describe(user="Người bị trừ tiền", amount="Số tiền")
async def trutien(interaction: discord.Interaction, user: discord.User, amount: int):
    if not await is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    
    target_id = str(user.id)
    await create_user_if_not_exists(target_id)
    success = await remove_money(target_id, amount, str(interaction.user.id))
    
    if success:
        embed = create_embed(title="💸 Trừ Tiền", description=f"Đã trừ **{amount:,} VNĐ** từ **{user.name}**!", color=COLOR_WARNING, thumbnail_url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Số dư không đủ hoặc có lỗi!", ephemeral=True)

@bot.tree.command(name="phatlixi", description="🧧 Phát lì xì cho tất cả người chơi (Admin)")
@app_commands.describe(amount="Số tiền mỗi người nhận")
async def phatlixi(interaction: discord.Interaction, amount: int):
    if not await is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
        return
    
    class LixiView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.claimed = set()
        
        @discord.ui.button(label="Nhận Lì Xì", style=discord.ButtonStyle.success, emoji="🧧")
        async def claim(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            user_id_btn = str(button_interaction.user.id)
            
            if user_id_btn in self.claimed:
                await button_interaction.response.send_message("❌ Bạn đã nhận lì xì rồi!", ephemeral=True)
                return
            
            await create_user_if_not_exists(user_id_btn)
            await add_money(user_id_btn, amount, str(interaction.user.id))
            self.claimed.add(user_id_btn)
            await button_interaction.response.send_message(f"🧧 Bạn đã nhận **{amount:,} VNĐ**! Chúc mừng năm mới! 🎉", ephemeral=True)
    
    embed = create_embed(
        title="🧧 LÌ XÌ MAY MẮN",
        description=f"{EMOJI_RED_ENVELOPE} **{interaction.user.name}** đã phát lì xì!\n\n💰 Giá trị: **{amount:,} VNĐ**\n\n{EMOJI_PARTY} Nhấn nút bên dưới để nhận!",
        color=COLOR_GOLD,
        thumbnail_url=interaction.user.display_avatar.url,
        footer_text="Mỗi người chỉ được nhận 1 lần"
    )
    
    await interaction.response.send_message("🧧 Đang chuẩn bị lì xì...")
    await asyncio.sleep(0.5)
    msg = await interaction.original_response()
    await msg.edit(content="🧧✨ Đang mở lì xì...")
    await asyncio.sleep(0.5)
    await msg.edit(content="🧧✨💰 Lì xì đã sẵn sàng!")
    await asyncio.sleep(0.3)
    await msg.edit(content=None, embed=embed, view=LixiView())

# ============================================
# LICH SU + AI + PHAN TICH
# ============================================
@bot.tree.command(name="lichsu", description="📋 Xem lịch sử giao dịch")
@check_cooldown("lichsu", COOLDOWN_NORMAL)
async def lichsu(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "lichsu")
    
    transactions = get_transactions_ref().where(
        filter=FieldFilter("userId", "==", user_id)
    ).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
    
    if not transactions:
        await interaction.response.send_message("📋 Bạn chưa có giao dịch nào!", ephemeral=True)
        return
    
    description = "**10 giao dịch gần nhất:**\n\n"
    
    for t in transactions:
        t_data = t.to_dict()
        trans_type = t_data.get("type", "unknown")
        amount = t_data.get("amount", 0)
        timestamp = t_data.get("timestamp")
        target_id = t_data.get("targetId")
        
        time_str = timestamp.strftime("%d/%m/%Y %H:%M") if isinstance(timestamp, datetime) else "N/A"
        
        type_emoji = {"transfer": "💸", "loan": "💳", "repay": "✅", "addmoney": "💰", "trutien": "📉", "shop": "🛒", "lodit": "🎯", "anxin": "🙏"}.get(trans_type, "📄")
        type_name = {"transfer": "Chuyển tiền", "loan": "Vay tiền", "repay": "Trả nợ", "addmoney": "Nhận tiền", "trutien": "Trừ tiền", "shop": "Mua hàng", "lodit": "Chơi lỗ đít", "anxin": "Xin tiền"}.get(trans_type, trans_type)
        
        target_text = ""
        if target_id:
            try:
                member = interaction.guild.get_member(int(target_id))
                target_text = f" → **{member.name}**" if member else ""
            except:
                pass
        
        sign = "+" if amount > 0 and trans_type not in ["trutien", "shop"] else ""
        description += f"{type_emoji} **{type_name}**: {sign}{amount:,} VNĐ{target_text}\n└ 📅 {time_str}\n\n"
    
    embed = create_embed(title="📋 Lịch Sử Giao Dịch", description=description, color=COLOR_INFO, thumbnail_url=interaction.user.display_avatar.url, footer_text=f"Người chơi: {interaction.user.name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="doan", description="🤖 AI dự đoán Tài Xỉu")
@check_cooldown("doan", COOLDOWN_NORMAL)
async def doan(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "doan")
    
    games = get_game_history_ref().order_by("createdAt", direction=firestore.Query.DESCENDING).limit(20).get()
    game_list = [doc.to_dict() for doc in games]
    
    if len(game_list) < 5:
        await interaction.response.send_message("🤖 Cần ít nhất 5 ván gần nhất để dự đoán!", ephemeral=True)
        return
    
    tai_count = sum(1 for g in game_list if g.get("taiOrXiu") == "tai")
    xiu_count = sum(1 for g in game_list if g.get("taiOrXiu") == "xiu")
    total = tai_count + xiu_count
    tai_percent = (tai_count / total * 100) if total > 0 else 50
    confidence = 50 + random.randint(0, 15)
    
    if tai_count > xiu_count:
        prediction = f"{EMOJI_TAI} TÀI"
        pred_reason = "Xu hướng đang nghiêng về Tài"
    elif xiu_count > tai_count:
        prediction = f"{EMOJI_XIU} XỈU"
        pred_reason = "Xu hướng đang nghiêng về Xỉu"
    else:
        prediction = random.choice([f"{EMOJI_TAI} TÀI", f"{EMOJI_XIU} XỈU"])
        pred_reason = "Cân bằng, chọn ngẫu nhiên"
    
    embed = create_embed(
        title="🤖 AI Predictor",
        description=f"**Dự đoán dựa trên {total} ván gần nhất**\n\n📊 Độ tin cậy: **{confidence}%**\n\n🎯 Dự đoán: **{prediction}**\n📝 Lý do: {pred_reason}",
        color=COLOR_INFO,
        fields=[
            (f"{EMOJI_TAI} Tài gần đây", f"{tai_count}/{total} ({tai_percent:.0f}%)", True),
            (f"{EMOJI_XIU} Xỉu gần đây", f"{xiu_count}/{total} ({100-tai_percent:.0f}%)", True),
        ],
        footer_text="⚠️ Dự đoán chỉ mang tính tham khảo!"
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="phantich", description="📊 Phân tích xu hướng Tài Xỉu")
@check_cooldown("phantich", COOLDOWN_NORMAL)
async def phantich(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    cooldown_manager.set_cooldown(user_id, "phantich")
    
    await interaction.response.send_message("⏳ Đang thu thập dữ liệu...")
    msg = await interaction.original_response()
    await asyncio.sleep(0.8)
    await msg.edit(content="📊 Đang phân tích...")
    await asyncio.sleep(0.8)
    await msg.edit(content="🎯 Đang dự đoán...")
    await asyncio.sleep(0.8)
    
    games = get_game_history_ref().order_by("createdAt", direction=firestore.Query.DESCENDING).limit(20).get()
    game_list = [doc.to_dict() for doc in games]
    
    if len(game_list) < 5:
        await msg.edit(content="❌ Cần ít nhất 5 ván gần nhất để phân tích!")
        return
    
    tai_count = sum(1 for g in game_list if g.get("taiOrXiu") == "tai")
    xiu_count = sum(1 for g in game_list if g.get("taiOrXiu") == "xiu")
    total = tai_count + xiu_count
    
    current_streak = 0
    streak_type = None
    for g in game_list:
        if g.get("taiOrXiu") == "triple":
            continue
        if streak_type is None:
            streak_type = g.get("taiOrXiu")
            current_streak = 1
        elif g.get("taiOrXiu") == streak_type:
            current_streak += 1
        else:
            break
    
    streak_text = f"{current_streak} ván {streak_type} liên tiếp" if streak_type else "Không có"
    confidence = 50 + min(len(game_list), 29)
    
    if tai_count > xiu_count:
        prediction = f"{EMOJI_TAI} TÀI"
    elif xiu_count > tai_count:
        prediction = f"{EMOJI_XIU} XỈU"
    else:
        prediction = random.choice([f"{EMOJI_TAI} TÀI", f"{EMOJI_XIU} XỈU"])
    
    tai_percent = (tai_count / total * 100) if total > 0 else 50
    
    embed = create_embed(
        title="📊 Phân Tích Tài Xỉu",
        description=f"**20 ván gần nhất**\n\n{EMOJI_TAI} Tài: **{tai_count}/{total} ({tai_percent:.0f}%)**\n{EMOJI_XIU} Xỉu: **{xiu_count}/{total} ({100-tai_percent:.0f}%)**\n\n🔥 Chuỗi hiện tại: **{streak_text}**\n🎯 Độ tin cậy: **{confidence}%**\n\n🔮 Dự đoán: **{prediction}**",
        color=COLOR_INFO,
        footer_text="⚠️ Dự đoán chỉ mang tính tham khảo"
    )
    await msg.edit(content=None, embed=embed)

# ============================================
# ERROR HANDLER
# ============================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(f"⏰ Vui lòng đợi {error.retry_after:.0f} giây!", ephemeral=True)
    elif isinstance(error, app_commands.errors.CheckFailure):
        pass
    else:
        print(f"Command error: {error}")
        try:
            await interaction.response.send_message("❌ Có lỗi xảy ra, vui lòng thử lại!", ephemeral=True)
        except:
            pass

# ============================================
# HTTP SERVER
# ============================================
async def health_check(request):
    return web.Response(text=json.dumps({"status": "online", "bot": str(bot.user) if bot.user else "Starting...", "guilds": len(bot.guilds), "latency": f"{bot.latency * 1000:.2f}ms" if bot.ws else "N/A", "timestamp": datetime.now(timezone.utc).isoformat()}), content_type="application/json")

async def dashboard(request):
    return web.Response(text=f"<!DOCTYPE html><html><head><title>Discord Casino Bot</title><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'><style>body{{font-family:Arial;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:linear-gradient(135deg,#667eea,#764ba2);color:white}}.container{{text-align:center;background:rgba(255,255,255,.1);padding:40px;border-radius:20px}}</style></head><body><div class='container'><h1>🎰 Discord Casino Bot</h1><p style='color:#4ade80;font-size:24px'>🟢 Online</p><p>🤖 {str(bot.user) if bot.user else 'Loading...'}</p><p>📡 {len(bot.guilds)} servers</p></div></body></html>", content_type="text/html")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', dashboard)
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web server started on port {port}")

# ============================================
# RUN
# ============================================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN not found!")
        exit(1)
    
    print("🚀 Starting Discord Casino Bot...")
    
    @bot.event
    async def setup_hook():
        await start_web_server()
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
