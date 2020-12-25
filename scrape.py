#!/usr/bin/env python
import os
import re
import sys
import json
import argparse

try:
  import googleapiclient.discovery as gapi 
  import googleapiclient.errors
  import google.auth.exceptions

except ImportError as err:
  print("Failed to import a required dependency: {0}".format(err))
  exit(1)

program_description = "Scrape Youtube video descriptions using a regex"

def make_request(req: gapi.HttpRequest):
  """Execute a Google Api request return it's response"""
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


def get_video_data(api:gapi.Resource, id_list: list) -> list:
  """Using a list of video ID's, return a list of titles and descriptions"""
  ids = ''
  out = []
  count = 0
  for vid in id_list:
    if count <= 49:
      if ids == "":
        ids = vid
      else:
        ids = "%s,%s" % (ids, vid)
      count = count + 1 
    else:
      print("Getting %d videos: %s" % (count, ids), file=sys.stderr)
      response = make_request(api.videos().list(
        id=ids,
        part='snippet',
        maxResults=50
      ))

      for data in response['items']:
        print("Added to list: %s" % (data['snippet']['title']), file=sys.stderr)
        out.append([
          data['snippet']['title'],
          data['snippet']['description']
        ])

      ids = ""
      count = 0

  if count != 0:
    print("Getting %d videos: %s" % (count, ids), file=sys.stderr)
    response = make_request(api.videos().list(
      id=ids,
      part='snippet',
      maxResults=50
    ))

    for data in response['items']:
      print("Added to list: %s" % (data['snippet']['title']), file=sys.stderr)
      out.append([
        data['snippet']['title'],
        data['snippet']['description']
      ])
  return out


def output_video_data(m_re: re.Pattern, video_data: list) -> bool:
  """Output all strings that match a given regex from a list of strings"""
  print("Processing %d videos: %s" % (len(video_data), m_re), file=sys.stderr)
  if len(video_data) > 0:
    for data in video_data:
      m = m_re.search(data[1])
      if m is not None:
        print(m[0])
  else:
    print("output_video_data: got empty data list", file=sys.stderr)
    return False
  return True


def main(api: gapi.Resource, relist: list, id: str):
  video_ids = []

  # We only need the first item, since we're operating on one channel
  print("Starting scrape", file=sys.stderr)
  print("Getting channel: %s" % id, file=sys.stderr)
  channel = make_request(api.channels().list(part="contentDetails", id=id))['items'][0]

  # Get the uploaded videos playlist
  playlist_id = channel['contentDetails']['relatedPlaylists']['uploads']
  print("Getting playlist ID: %s" % playlist_id, file=sys.stderr)
  playlist = make_request(api.playlistItems().list(
    playlistId=playlist_id,
    part='contentDetails',
    maxResults=10
  ))

  next_page     = playlist['nextPageToken']
  total_results = playlist['pageInfo']['totalResults']
  results_per   = playlist['pageInfo']['resultsPerPage']
  total_pages   = total_results // results_per

  if total_results < 1:
    print("The channel %s has no uploaded videos" % (id), file=sys.stderr)
    exit(0)

  # Just append to an array. We can clean this up later.
  for video in playlist['items']:
    video_ids.append(video['contentDetails']['videoId'])

  # Sub 1, since we already grabbed a page. This way, we don't grab more than
  # we need.
  for _ in range(0, total_pages - 1 ):
    playlist = make_request(api.playlistItems().list(
      playlistId=playlist_id,
      part='contentDetails',
      maxResults=10,
      pageToken=next_page
    ))

    for v in playlist['items']:
      video_ids.append(v['contentDetails']['videoId'])

    # If the next pageToken is nil or blank, then we're done.
    try:
      next_page = playlist['nextPageToken']
    except KeyError:
      break
    if next_page == "":
      break

  [output_video_data(re, get_video_data(api, video_ids)) for re in relist]


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=program_description)

  parser.add_argument("--regex", "-r", 
    metavar='<regex>', type=str, action='append')
  parser.add_argument("--channel-id", "-c",
    metavar='<channel>', type=str, action='store')
  parser.add_argument("--api-key", "-k",
    metavar='<key>', type=str, action='store')

  args = parser.parse_args()

  try:
    key = args.key
  except AttributeError:
    try:
      key = os.environ['API_KEY']
    except KeyError:
      print("Please supply a valid API key, and channel.",
        file=sys.stderr)
      exit(1)
  
  try:
    channel = args.channel
  except AttributeError:
    try:
      channel = os.environ['CHANNEL_ID']
    except KeyError:
      print("Please supply a valid API key, and channel.",
        file=sys.stderr)
      exit(1)

  try:
    regex = args.regex
  except AttributeError:
    print("Please supply a valid regex capture.",
      file=sys.stderr)
    exit(1)

  regex_list = [re.compile(capture) for capture in args.regex]

  try:
    main(id=channel, relist=regex_list,
      api=gapi.build("youtube", "v3", developerKey=key))
  except google.auth.exceptions.DefaultCredentialsError:
    print("Please supply a valid API key (API_KEY)", file=sys.stderr)
    exit(1)