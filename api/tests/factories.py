import factory.fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from core.models import Wish, WishList, WishListUser

faker = Faker("fr_FR")


class WishListFactory(DjangoModelFactory):
    wishlist_name = factory.LazyAttribute(lambda _: faker.sentence())

    class Meta:
        model = WishList
        django_get_or_create = ("wishlist_name",)


class WishListUserFactory(DjangoModelFactory):
    name = factory.LazyAttribute(lambda _: faker.name())
    wishlist = factory.SubFactory(WishListFactory)

    class Meta:
        model = WishListUser
        django_get_or_create = ("name", "wishlist")


class WishFactory(DjangoModelFactory):
    name = factory.LazyAttribute(lambda _: faker.word())
    wishlist_user = factory.SubFactory(WishListUserFactory)

    class Meta:
        model = Wish
