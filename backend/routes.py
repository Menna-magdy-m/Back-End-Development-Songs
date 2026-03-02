from . import app
import os
import json
import pymongo
from flask import jsonify, request, make_response, abort, url_for  # noqa; F401
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId
import sys

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list: list = json.load(open(json_url))

# client = MongoClient(
#     f"mongodb://{app.config['MONGO_USERNAME']}:{app.config['MONGO_PASSWORD']}@localhost")
mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')
mongodb_port = os.environ.get('MONGODB_PORT')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service == None:
    app.logger.error('Missing MongoDB server in the MONGODB_SERVICE variable')
    # abort(500, 'Missing MongoDB server in the MONGODB_SERVICE variable')
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"


print(f"connecting to url: {url}")

try:
    client = MongoClient(url)
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")

db = client.songs
db.songs.drop()
db.songs.insert_many(songs_list)

def parse_json(data):
    return json.loads(json_util.dumps(data))

######################################################################
# INSERT CODE HERE
######################################################################
@app.route("/health")
def index_explicit():
    """Return 'Hello World' message with a status code of 200.

    Returns:
        response: A response object containing the message and status code 200.
    """
    # Create a response object with the message "Hello World"
    resp = make_response({"message": "Health"})
    # Set the status code of the response to 200
    resp.status_code = 200
    # Return the response object
    return resp

@app.route("/count")
def count():
    """return length of data"""
    count = db.songs.count_documents({})

    return {"count": count}, 200
    
@app.route("/song")
def songs():
    """Returns all songs from the database as a list."""
    
    # 1. Fetch all documents
    results = list(db.songs.find({}))

    # 2. Convert MongoDB ObjectIds to strings so JSON can handle them
    for song in results:
        song["_id"] = str(song["_id"])

    # 3. Return the sanitized list
    return {"songs": results}, 200

@app.route("/song/<int:id>", methods=["GET"])
def get_song_by_id(id):
    """Find a song by its custom ID and return it."""
    
    # 1. Search for the song in the database using the provided id
    song = db.songs.find_one({"id": id})

    # 2. Check if the song exists
    if not song:
        # Return 404 if no document matches the id
        return {"message": "song with id not found"}, 404

    # 3. If found, convert the internal MongoDB _id to a string to avoid JSON errors
    song["_id"] = str(song["_id"])

    # 4. Return the song data with a 200 OK status
    return song, 200

@app.route("/song", methods=["POST"])
def create_song():
    """Extracts song data from the request body and saves it to the database."""
    
    # 1. Extract the song data from the request body (JSON)
    new_song = request.get_json()
    
    # 2. Extract the 'id' from the incoming data
    song_id = new_song.get("id")

    # 3. Check if a song with that 'id' already exists in the database
    existing_song = db.songs.find_one({"id": song_id})

    if existing_song:
        # Return 302 (Found/Redirect) if the ID is already taken
        return {"Message": f"song with id {song_id} already present"}, 302

    # 4. If it doesn't exist, insert the new song into the database
    insert_result = db.songs.insert_one(new_song)

    # 5. Return the newly created song ID and a 201 Created status
    return {"inserted_id": str(insert_result.inserted_id)}, 201

@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    """Update a song and return the full document in Extended JSON format."""
    
    # 1. Get the update data from the request body
    song_data = request.get_json()

    # 2. Check if the song exists
    song = db.songs.find_one({"id": id})
    if song is None:
        return {"message": "song not found"}, 404

    # 3. Perform the update
    # We use $set to only change the fields provided in the request
    db.songs.update_one({"id": id}, {"$set": song_data})

    # 4. Fetch the updated document to return it
    updated_song = db.songs.find_one({"id": id})

    # 5. Convert to Extended JSON (to get the "$oid" format)
    # json_util.dumps handles the MongoDB ObjectId
    response_json = json.loads(json_util.dumps(updated_song))

    # 6. Return with 201 CREATED as per your requirement
    return response_json, 201

@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):
    """Deletes a song by its ID and returns the appropriate status code."""
    
    # 1. Attempt to delete the document with the matching 'id'
    delete_result = db.songs.delete_one({"id": id})

    # 2. Check the deleted_count attribute
    if delete_result.deleted_count == 0:
        # If no document was deleted, the ID didn't exist
        return {"message": "song not found"}, 404

    # 3. If deleted_count is 1, return an empty body with 204 NO CONTENT
    # In Flask, returning an empty string "" or None with 204 works perfectly
    return "", 204