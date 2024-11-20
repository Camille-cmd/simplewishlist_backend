# Class to handle the Redis cache connection and operations for the WishList
import json

from core.models import WishListUser
from django.core.cache import cache


class RedisForWishList:
    """Cache backend was set to use the default redis cache alias"""

    def __init__(self):
        self.timeout = 60 * 60 * 24  # 24 hours

    def get_currently_connected_users(self, room_group_name: str, current_user: WishListUser) -> list:
        """
        Get the list of currently connected users in the group via Redis
        Save the user in the group if it is not already in it
        Usernames are unique, so no need to check for duplicates
        """
        if not cache.get(room_group_name):
            # If the room does not exist, we create it and add the user
            room_connected_users = [current_user.name]
            cache.set(room_group_name, json.dumps(room_connected_users), timeout=self.timeout)
        else:
            # If the room exists, we add the user to the list when it is not already in it
            room_connected_users = json.loads(cache.get(room_group_name))
            if current_user.name not in room_connected_users:
                room_connected_users.append(current_user.name)
                cache.set(room_group_name, json.dumps(room_connected_users), timeout=self.timeout)

        return room_connected_users

    def remove_user_from_connected_users(self, room_group_name: str, current_user: WishListUser) -> list:
        """Remove the user from the connected users in the group"""
        room_connected_users = []
        if cache.get(room_group_name):
            # Get the list of connected users and remove the current user
            room_connected_users = json.loads(cache.get(room_group_name))
            room_connected_users.remove(current_user.name)
            if not room_connected_users:
                # If the room is empty, we delete it
                cache.delete(room_group_name)
            else:
                # If the room is not empty, we update the list of connected users
                cache.set(room_group_name, json.dumps(room_connected_users), timeout=self.timeout)

        return room_connected_users
