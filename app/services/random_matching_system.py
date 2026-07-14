#!/usr/bin/env python3
"""
Random Battle Matching System
Clean implementation of random opponent selection, skill-based matching, and queue management
"""

import asyncio
import websockets
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

class User:
    def __init__(self, user_id: int, username: str, websocket=None):
        self.user_id = user_id
        self.username = username
        self.websocket = websocket
        self.current_battle = None
        self.side = None
        self.stats = {
            'wins': 0,
            'losses': 0,
            'battles_completed': 0,
            'skill_level': 'intermediate',
            'elo_rating': 1200,
            'preferences': {
                'preferred_side': None,
                'max_rounds': 3,
                'time_limit': 300
            }
        }
        self.in_queue = False
        self.queue_joined_at = None

class BattleRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants = {}
        self.messages = []
        self.arguments = {'pro': [], 'con': []}
        self.current_round = 1
        self.max_rounds = 3
        self.round_time_limit = 300
        self.status = 'waiting'
        self.created_at = datetime.now()
        self.started_at = None
        self.round_started_at = None
        self.round_ends_at = None
        self.completed_at = None
        self.winner_side = None
        self.winner_user_id = None

class MatchmakingQueue:
    def __init__(self):
        self.queue = []
        self.processing = False
        self.last_process_time = None
        self.match_history = []
        
    def add_to_queue(self, user: User, preferences: Dict = None):
        """Add user to matchmaking queue"""
        if user.in_queue:
            print(f"⚠️ {user.username} already in queue")
            return False
        
        user.in_queue = True
        user.queue_joined_at = datetime.now()
        
        queue_entry = {
            'user': user,
            'preferences': preferences or {},
            'added_at': datetime.now(),
            'estimated_wait_time': None
        }
        
        self.queue.append(queue_entry)
        print(f"🎲 {user.username} added to matchmaking queue (Position {len(self.queue)})")
        
        return True
    
    def remove_from_queue(self, user: User):
        """Remove user from queue"""
        self.queue = [entry for entry in self.queue if entry['user'].user_id != user.user_id]
        user.in_queue = False
        user.queue_joined_at = None
        print(f"👋 {user.username} removed from queue")
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return len(self.queue)
    
    def get_wait_time_estimate(self, user: User) -> str:
        """Calculate estimated wait time for user"""
        if not user.in_queue:
            return "Not in queue"
        
        position = next((i for i, entry in enumerate(self.queue) if entry['user'].user_id == user.user_id), 0)
        if position == -1:
            return "Not in queue"
        
        # Estimate 30 seconds per match
        avg_match_time = 30
        matches_ahead = position // 2
        estimated_wait = matches_ahead * avg_match_time
        
        return f"{estimated_wait} seconds"
    
    def process_queue(self) -> List[Dict]:
        """Process queue and create matches"""
        if self.processing or len(self.queue) < 2:
            return []
        
        self.processing = True
        self.last_process_time = datetime.now()
        
        print(f"\n🔄 Processing matchmaking queue ({len(self.queue)} users waiting)...")
        
        matches_created = []
        
        # Process queue in pairs
        while len(self.queue) >= 2:
            # Get first two users
            user1_entry = self.queue.pop(0)
            user2_entry = self.queue.pop(0)
            
            user1 = user1_entry['user']
            user2 = user2_entry['user']
            
            # Check compatibility
            if self.is_compatible_match(user1, user2):
                # Create match
                match = self.create_match(user1, user2)
                matches_created.append(match)
                
                # Remove users from queue
                self.remove_from_queue(user1)
                self.remove_from_queue(user2)
                
                print(f"🎯 Match found: {user1.username} vs {user2.username}")
            else:
                # Put users back at end of queue
                self.queue.append(user1_entry)
                self.queue.append(user2_entry)
                break
        
        self.processing = False
        print(f"📋 Queue processed. Created {len(matches_created)} matches")
        
        return matches_created
    
    def is_compatible_match(self, user1: User, user2: User) -> bool:
        """Check if two users are compatible for matching"""
        # Basic compatibility checks
        if user1.user_id == user2.user_id:
            return False
        
        if user1.current_battle is not None or user2.current_battle is not None:
            return False
        
        # Skill level compatibility (same level or adjacent)
        skill_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        user1_level_idx = skill_levels.index(user1.stats['skill_level'])
        user2_level_idx = skill_levels.index(user2.stats['skill_level'])
        
        if abs(user1_level_idx - user2_level_idx) > 1:
            return False
        
        # ELO rating compatibility (within 300 points)
        elo_diff = abs(user1.stats['elo_rating'] - user2.stats['elo_rating'])
        if elo_diff > 300:
            return False
        
        return True
    
    def create_match(self, user1: User, user2: User) -> Dict:
        """Create a match between two users"""
        battle_id = f"battle_{int(time.time())}"
        
        # Assign sides randomly
        if random.random() < 0.5:
            user1.side = 'pro'
            user2.side = 'con'
        else:
            user1.side = 'con'
            user2.side = 'pro'
        
        # Create battle room
        battle_room = BattleRoom(battle_id)
        battle_room.participants[user1.user_id] = user1
        battle_room.participants[user2.user_id] = user2
        
        # Update user states
        user1.current_battle = battle_id
        user2.current_battle = battle_id
        
        # Record match
        match = {
            'battle_id': battle_id,
            'user1': user1,
            'user2': user2,
            'battle_room': battle_room,
            'created_at': datetime.now(),
            'matching_method': 'random_queue'
        }
        
        self.match_history.append(match)
        
        return match
    
    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        return {
            'queue_size': len(self.queue),
            'processing': self.processing,
            'last_process_time': self.last_process_time.isoformat() if self.last_process_time else None,
            'total_matches_created': len(self.match_history),
            'users_waiting': [entry['user'].username for entry in self.queue]
        }

class RandomMatchingSystem:
    def __init__(self):
        self.users = {}
        self.matchmaking_queue = MatchmakingQueue()
        self.active_battles = {}
        self.websocket_connections = {}
        
        print("🚀 Random Battle Matching System Starting...")
        print("=" * 60)
        print("📋 Features:")
        print("✅ Random opponent selection")
        print("✅ Skill-based matching")
        print("✅ ELO rating system")
        print("✅ Queue management")
        print("✅ Automatic battle pairing")
        print("✅ Real-time notifications")
        print("=" * 60)
    
    async def register_user(self, user_id: int, username: str, websocket, skill_level: str = 'intermediate'):
        """Register a new user"""
        user = User(user_id, username, websocket)
        user.stats['skill_level'] = skill_level
        
        self.users[user_id] = user
        self.websocket_connections[websocket] = user_id
        
        print(f"👤 {username} (ID: {user_id}) registered with skill level {skill_level}")
        
        # Send welcome message
        await self.send_to_user(user, {
            'type': 'user_registered',
            'data': {
                'user_id': user_id,
                'username': username,
                'skill_level': skill_level,
                'elo_rating': user.stats['elo_rating']
            }
        })
        
        return user
    
    async def handle_websocket(self, websocket, path):
        """Handle WebSocket connections"""
        print(f"🔗 New connection from {path}")
        
        try:
            # Extract user info from path
            if path.startswith('/battle/'):
                room_id = path.split('/')[-1]
                user_id = int(path.split('/')[-2]) if len(path.split('/')) > 2 else None
            else:
                room_id = None
                user_id = None
            
            if not user_id:
                await websocket.close()
                return
            
            # Get or register user
            if user_id not in self.users:
                user = await self.register_user(user_id, f"User{user_id}", websocket)
            else:
                user = self.users[user_id]
                user.websocket = websocket
                self.websocket_connections[websocket] = user_id
            
            # Handle messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(user, data)
                except json.JSONDecodeError:
                    await self.send_to_user(user, {
                        'type': 'error',
                        'data': {'message': 'Invalid JSON format'}
                    })
                except Exception as e:
                    print(f"❌ Error handling message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            print(f"👋 User {user_id if user_id else 'unknown'} disconnected")
            if user_id and user_id in self.users:
                user = self.users[user_id]
                self.matchmaking_queue.remove_from_queue(user)
                del self.websocket_connections[websocket]
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
    
    async def handle_message(self, user: User, data: Dict):
        """Handle incoming messages from users"""
        msg_type = data.get('type')
        
        print(f"📨 {user.username}: {msg_type}")
        
        if msg_type == 'find_battle':
            await self.handle_find_battle(user, data)
        elif msg_type == 'join_queue':
            await self.handle_join_queue(user, data)
        elif msg_type == 'leave_queue':
            await self.handle_leave_queue(user, data)
        elif msg_type == 'queue_status':
            await self.send_queue_status(user)
        elif msg_type == 'start_battle':
            await self.handle_start_battle(user, data)
        elif msg_type == 'submit_argument':
            await self.handle_submit_argument(user, data)
        elif msg_type == 'chat':
            await self.handle_chat_message(user, data)
        elif msg_type == 'leave_battle':
            await self.handle_leave_battle(user, data)
        elif msg_type == 'heartbeat':
            await self.send_to_user(user, {'type': 'heartbeat_response'})
        else:
            print(f"❓ Unknown message type: {msg_type}")
    
    async def handle_find_battle(self, user: User, data: Dict):
        """Handle find battle request"""
        preferences = data.get('data', {})
        skill_level = preferences.get('skill_level', user.stats['skill_level'])
        
        # Try to find immediate match
        available_opponents = [
            u for u in self.users.values()
            if u.user_id != user.user_id 
            and u.in_queue 
            and u.current_battle is None
            and self.matchmaking_queue.is_compatible_match(user, u)
        ]
        
        if available_opponents:
            # Found opponent, create immediate match
            opponent = random.choice(available_opponents)
            match = self.matchmaking_queue.create_match(user, opponent)
            
            # Add to active battles
            self.active_battles[match['battle_id']] = match['battle_room']
            
            # Notify both users
            await self.notify_match_created(match)
            
            print(f"🎯 Immediate match found: {user.username} vs {opponent.username}")
        else:
            # No immediate match, add to queue
            await self.handle_join_queue(user, data)
    
    async def handle_join_queue(self, user: User, data: Dict):
        """Handle join queue request"""
        preferences = data.get('data', {})
        
        if self.matchmaking_queue.add_to_queue(user, preferences):
            await self.send_queue_status(user)
            
            # Process queue for potential matches
            matches = self.matchmaking_queue.process_queue()
            
            for match in matches:
                self.active_battles[match['battle_id']] = match['battle_room']
                await self.notify_match_created(match)
    
    async def handle_leave_queue(self, user: User, data: Dict):
        """Handle leave queue request"""
        self.matchmaking_queue.remove_from_queue(user)
        await self.send_queue_status(user)
    
    async def send_queue_status(self, user: User):
        """Send current queue status to user"""
        status = self.matchmaking_queue.get_queue_status()
        wait_time = self.matchmaking_queue.get_wait_time_estimate(user)
        
        await self.send_to_user(user, {
            'type': 'queue_status',
            'data': {
                'queue_size': status['queue_size'],
                'in_queue': user.in_queue,
                'estimated_wait_time': wait_time,
                'users_waiting': status['users_waiting']
            }
        })
    
    async def handle_start_battle(self, user: User, data: Dict):
        """Handle battle start"""
        battle_id = data.get('data', {}).get('battle_id')
        
        if not battle_id or battle_id not in self.active_battles:
            await self.send_to_user(user, {
                'type': 'error',
                'data': {'message': 'Battle not found'}
            })
            return
        
        battle_room = self.active_battles[battle_id]
        
        # Don't set status here - let the debate_service.start_battle handle it
        # Just forward the request to the proper service
        print(f"🚀 Battle start requested for {battle_id}, forwarding to debate service")
        
        # Call the proper debate service to start the battle
        from app.services.debate_service import DebateService
        from app.database import get_db
        
        db = next(get_db())
        debate_service = DebateService(db)
        
        try:
            started_battle = debate_service.start_battle(battle_room_id=battle_id)
            print(f"✅ Battle {battle_id} started properly via debate service")
            
            # Notify all participants
            await self.notify_battle_participants(battle_room, {
                'type': 'battle_started',
                'data': {
                    'battle_id': battle_id,
                    'message': 'Battle has begun! Round 1 starts now!',
                    'current_round': started_battle.current_round,
                    'max_rounds': started_battle.max_rounds
                }
            })
        except ValueError as e:
            await self.send_to_user(user, {
                'type': 'error',
                'data': {'message': str(e)}
            })
        finally:
            db.close()
    
    async def handle_submit_argument(self, user: User, data: Dict):
        """Handle argument submission"""
        battle_id = data.get('data', {}).get('battle_id')
        round_number = data.get('data', {}).get('round_number', 1)
        argument = data.get('data', {}).get('argument')
        
        if not battle_id or battle_id not in self.active_battles:
            return
        
        battle_room = self.active_battles[battle_id]
        
        # Add argument to battle
        argument_data = {
            'id': f"arg_{int(time.time())}",
            'content': argument,
            'author': user.username,
            'timestamp': datetime.now().isoformat(),
            'side': user.side,
            'round': round_number
        }
        
        if user.side == 'pro':
            battle_room.arguments['pro'].append(argument_data)
        else:
            battle_room.arguments['con'].append(argument_data)
        
        print(f"💬 {user.username} ({user.side}) submitted argument for round {round_number}")
        
        # Notify all participants
        await self.notify_battle_participants(battle_room, {
            'type': 'argument_submitted',
            'data': {
                'round_number': round_number,
                'side': user.side,
                'argument': argument,
                'author': user.username,
                'quality_score': self.calculate_argument_quality(argument)
            }
        })
    
    async def handle_chat_message(self, user: User, data: Dict):
        """Handle chat messages"""
        battle_id = data.get('data', {}).get('battle_id')
        message = data.get('data', {}).get('message')
        
        if not battle_id or battle_id not in self.active_battles:
            return
        
        battle_room = self.active_battles[battle_id]
        
        # Add to chat history
        chat_data = {
            'author': user.username,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        battle_room.messages.append(chat_data)
        
        print(f"💬 {user.username}: {message}")
        
        # Notify all participants
        await self.notify_battle_participants(battle_room, {
            'type': 'chat',
            'data': chat_data
        })
    
    async def handle_leave_battle(self, user: User, data: Dict):
        """Handle leaving battle"""
        battle_id = data.get('data', {}).get('battle_id')
        
        if not battle_id or battle_id not in self.active_battles:
            return
        
        battle_room = self.active_battles[battle_id]
        
        # Remove user from battle
        if user.user_id in battle_room.participants:
            del battle_room.participants[user.user_id]
        
        user.current_battle = None
        user.side = None
        
        print(f"👋 {user.username} left battle {battle_id}")
        
        # Notify remaining participants
        await self.notify_battle_participants(battle_room, {
            'type': 'user_left',
            'data': {
                'user_id': user.user_id,
                'username': user.username
            }
        })
        
        # Clean up empty battles
        if len(battle_room.participants) == 0:
            del self.active_battles[battle_id]
            print(f"🗑️ Battle {battle_id} cleaned up")
    
    async def notify_match_created(self, match: Dict):
        """Notify users about match creation"""
        battle_room = match['battle_room']
        user1 = match['user1']
        user2 = match['user2']
        
        # Notify user1
        await self.send_to_user(user1, {
            'type': 'match_found',
            'data': {
                'battle_id': match['battle_id'],
                'opponent': {
                    'username': user2.username,
                    'skill_level': user2.stats['skill_level'],
                    'elo_rating': user2.stats['elo_rating']
                },
                'your_side': user1.side,
                'message': f"Match found! You will debate {user2.username} as {user1.side} side"
            }
        })
        
        # Notify user2
        await self.send_to_user(user2, {
            'type': 'match_found',
            'data': {
                'battle_id': match['battle_id'],
                'opponent': {
                    'username': user1.username,
                    'skill_level': user1.stats['skill_level'],
                    'elo_rating': user1.stats['elo_rating']
                },
                'your_side': user2.side,
                'message': f"Match found! You will debate {user1.username} as {user2.side} side"
            }
        })
    
    async def notify_battle_participants(self, battle_room: BattleRoom, message: Dict):
        """Notify all participants in a battle"""
        for participant in battle_room.participants.values():
            await self.send_to_user(participant, message)
    
    async def send_to_user(self, user: User, message: Dict):
        """Send message to specific user"""
        if user and user.websocket:
            try:
                await user.websocket.send(json.dumps(message))
            except:
                pass
    
    def calculate_argument_quality(self, argument: str) -> int:
        """Calculate argument quality score"""
        if not argument:
            return 5
        
        word_count = len(argument.split())
        
        # Simple quality metrics
        if word_count < 10:
            return 8  # Short and clear
        elif word_count < 25:
            return 7  # Good length
        elif word_count < 50:
            return 6  # Well-developed
        else:
            return 5  # Too long
        
        # Bonus for technical terms
        technical_terms = ['algorithm', 'data', 'AI', 'system', 'analysis', 'research']
        if any(term in argument.lower() for term in technical_terms):
            return min(10, 6 + 2)
        
        return min(10, word_count + 1)
    
    async def run_server(self):
        """Run the random matching server"""
        print("\n🌐 Starting WebSocket server on ws://localhost:8765")
        print("📝 Test Instructions:")
        print("1. Open browser and go to: ws://localhost:8765/battle/123/test")
        print("2. Use browser console to send commands:")
        print("   {'type': 'join_queue'} - Join matchmaking queue")
        print("   {'type': 'find_battle'} - Find immediate battle")
        print("   {'type': 'queue_status'} - Get queue status")
        print("   {'type': 'start_battle', 'data': {'battle_id': 'battle_123'}} - Start battle")
        print("   {'type': 'submit_argument', 'data': {'battle_id': 'battle_123', 'argument': 'Your argument'}} - Submit argument")
        print("   {'type': 'chat', 'data': {'battle_id': 'battle_123', 'message': 'Your message'}} - Send chat")
        print("=" * 50)
        print("⚡ Waiting for connections...")
        
        try:
            async with websockets.serve("localhost", 8765) as server:
                print("✅ Random matching server started successfully!")
                await server.wait_closed()
        except Exception as e:
            print(f"❌ Server error: {e}")

def main():
    """Main function"""
    matching_system = RandomMatchingSystem()
    
    try:
        asyncio.run(matching_system.run_server())
    except KeyboardInterrupt:
        print("\n🛑 Random matching system stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
