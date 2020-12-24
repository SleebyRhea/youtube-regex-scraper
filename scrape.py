#!/usr/local/env python
import os
import re
import sys
import json
from googleapiclient.discovery import build
import googleapiclient.errors
import google.auth.exceptions

max_results = 10

def make_request(req: googleapiclient.discovery.HttpRequest):
  try:
    res = req.execute()

  except googleapiclient.errors.HttpError as err:
    print("Failed to query Youtube API: {0}".format(err),
      file=sys.stderr)
    exit(1)

  except googleapiclient.errors.Error as err:
    print("make_request: failed to process the request: {0}".format(err),
      file=sys.stderr)
  
  return res


def main(api: googleapiclient.discovery.Resource, id: str):
  videos = []
  video_data = []

  print("Starting scrape", file=sys.stderr)
  print("Grabbing channel: %s" % id, file=sys.stderr)
  channel_data = make_request(api.channels().list(
    part="id,contentDetails",
    id="UCLBZcndRzbN92awmkpuTmDg" 
  ))

  playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

  print("Grabbing playlist ID: %s" % playlist_id, file=sys.stderr)
  playlist_data = make_request(api.playlistItems().list(
    playlistId=playlist_id,
    part='contentDetails',
    maxResults=max_results
  ))

  next_page     = playlist_data['nextPageToken']
  total_results = playlist_data['pageInfo']['totalResults']
  results_per   = playlist_data['pageInfo']['resultsPerPage']
  total_pages   = total_results // results_per

  if total_results < 1:
    print("That channel has no uploaded videos", file=sys.stderr)
    exit(0)

  # Just append to an array. We can clean this up later.
  for video in playlist_data['items']:
    videos.append([
      video['id'],
      video['etag'],
      video['contentDetails']['videoId']
    ])


  # Sub 1, since we already grabbed a page. This way, we don't grab more than
  # we need.
  for _ in range(0, total_pages - 1 ):
    playlist_data = make_request(api.playlistItems().list(
      playlistId=playlist_id,
      part='contentDetails',
      maxResults=max_results,
      pageToken=next_page
    ))

    for video in playlist_data['items']:
      videos.append([
        video['id'],
        video['etag'],
        video['contentDetails']['videoId']
      ])

    # If the next pageToken is nil or blank, then we're done.
    try:
      next_page = playlist_data['nextPageToken']
    except KeyError:
      break
    if next_page == "":
      break

  ids=''
  count = 0
  for video_def in videos:
    if count <= 49:
      if ids == "":
        ids = video_def[2]
      else:
        ids = "{0},{1}".format(ids, video_def[2])
      count = count + 1 
    else:
      print("Getting %d videos: %s" % (count, ids), file=sys.stderr)

      videos = make_request(api.videos().list(
        id=ids,
        part='snippet',
        maxResults=50
      ))

      for data in videos['items']:
        video_data.append([
          data['snippet']['title'],
          data['snippet']['description']
        ])

      ids = ""
      count = 0

  if count != 0:
    print("Getting %d videos: %s" % (count, ids), file=sys.stderr)
    videos = make_request(api.videos().list(
      id=ids,
      part='snippet',
      maxResults=50
    ))

    for data in videos['items']:
      video_data.append([
        data['snippet']['title'],
        data['snippet']['description']
      ])

  drop_re = r'(https?://(?:www\.)?dropbox.com/s/[0-9a-zA-Z]+/[0-9a-z%A-Z ]+?.[mM][pP]3(:\?dl=[0-9]+)?)'

  for data in video_data:
    m = re.search(drop_re, data[1])
    if m:
      print(m.group(1))


if __name__ == "__main__":
  try:
    key = os.environ['API_KEY']
    channel = os.environ['CHANNEL_ID']
  except KeyError:
    print("Please supply a valid API key (API_KEY), and channel (CHANNEL_ID)",
      file=sys.stderr)
    exit(1)
  
  try:
    main(id=channel, api=build("youtube", "v3", developerKey=key))
  except google.auth.exceptions.DefaultCredentialsError as error:
    print("Please supply a valid API key (API_KEY)", file=sys.stderr)