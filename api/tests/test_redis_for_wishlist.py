# REDIS CACHE TESTS
import json

from django.core.cache import cache

from api.RedisForWishList import RedisForWishList
from api.tests.utils import SimpleWishlistBaseTestCase


class TestRedisForWishList(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_for_wishlist = RedisForWishList()
        cache.clear()

    def tearDown(self):
        # super().tearDown()
        cache.clear()

    def test_room_does_not_exist_creates_room_and_adds_user(self):
        """Test that the WishlistConsumer creates the room and adds the user to it if it does not exist."""
        cache.clear()
        current_user = self.user
        room_group_name = "test_room"

        result = self.redis_for_wishlist.get_currently_connected_users(room_group_name, current_user)

        self.assertEqual(result, [self.user.name])

        # Check that the cache variable was set
        self.assertEqual(json.loads(cache.get(room_group_name)), [self.user.name])

    def test_room_exists_adds_user(self):
        """Test that the WishlistConsumer adds the user to the room if it is not already in it."""
        # A user is already in the room, so the consumer should add the second user
        current_user = self.second_user
        room_group_name = "test_room"
        cache.set("test_room", json.dumps([self.user.name]))

        result = self.redis_for_wishlist.get_currently_connected_users(room_group_name, current_user)

        self.assertEqual(result, [self.user.name, self.second_user.name])
        self.assertEqual(json.loads(cache.get(room_group_name)), [self.user.name, self.second_user.name])

    def test_room_exists_user_already_in_the_room(self):
        """Test that the WishlistConsumer does not add the user to the room if it is already in it."""
        cache.set("test_room", json.dumps([self.user.name]))
        current_user = self.user
        room_group_name = "test_room"

        result = self.redis_for_wishlist.get_currently_connected_users(room_group_name, current_user)

        self.assertEqual(result, [self.user.name])
        self.assertEqual(json.loads(cache.get(room_group_name)), [self.user.name])

    def test_remove_user_from_room(self):
        """Test that the WishlistConsumer removes the user from the room."""
        cache.set("test_room", json.dumps([self.user.name]))
        current_user = self.user
        room_group_name = "test_room"

        result = self.redis_for_wishlist.remove_user_from_connected_users(room_group_name, current_user)

        self.assertEqual(result, [])
        self.assertIsNone(cache.get(room_group_name))

    def test_remove_user_but_keep_cache_if_other_users(self):
        """
        Test that the WishlistConsumer removes the user from the room but keeps the cache variable
        if other users are still connected.
        """
        cache.set("test_room", json.dumps([self.user.name, self.second_user.name]))
        current_user = self.user
        room_group_name = "test_room"

        result = self.redis_for_wishlist.remove_user_from_connected_users(room_group_name, current_user)

        self.assertEqual(result, [self.second_user.name])
        self.assertEqual(json.loads(cache.get(room_group_name)), [self.second_user.name])
