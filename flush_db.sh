docker exec -it simplewishlist_backend python manage.py flush --no-input
docker exec -it simplewishlist_backend python manage.py loaddata wishlist_data.json
