# this is an example of loading and iterating over a single file
# CREDIT TO: stuck_in_the_matrix, W. R.. (2026). Reddit comments/submissions 2005-06 to 2024-12 [Data set]. Academic Torrents. https://academictorrents.com/details/ba051999301b109eab37d16f027b3f49ade2de13
#
# Script Returns:
#   reply_edges.pkl       list of (replier, parent_author, created_utc, subreddit)
#                         one entry per comment = "replier wrote a direct reply to parent_author"
#   author_subreddits.pkl dict{author : list(subreddit)}  one entry per comment AND per post an author made
#   reddit_text.pkl       pandas DataFrame, one row per comment/post: author, kind, subreddit, created_utc, text
#                         (later scripts reuse this, so the raw .zst files only need to be read once)
import zstandard
import os
import sys
import json
from datetime import datetime, timezone
import logging.handlers
import pickle
from collections import defaultdict
import pandas as pd

#Logs:
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

#File Directories:'FINAL PROJECT/Reddit/reddit/comments/RC_2011-08.zst'
COMMENT_FILE = 'FINAL PROJECT/Reddit/reddit/comments/RC_2011-08.zst'
SUBMISSION_FILE = 'FINAL PROJECT/Reddit/reddit/submissions/RS_2011-08.zst' 
OUT_DIR = 'FINAL PROJECT/processed'

# Read Data:
def read_and_decode(reader, chunk_size, max_window_size, previous_chunk=None, bytes_read=0):
	chunk = reader.read(chunk_size)
	bytes_read += chunk_size
	if previous_chunk is not None:
		chunk = previous_chunk + chunk
	try:
		return chunk.decode()
	except UnicodeDecodeError:
		if bytes_read > max_window_size:
			raise UnicodeError(f"Unable to decode frame after reading {bytes_read:,} bytes")
		log.info(f"Decoding error with {bytes_read:,} bytes, reading another chunk")
		return read_and_decode(reader, chunk_size, max_window_size, chunk, bytes_read)


def read_lines_zst(file_name):
	with open(file_name, 'rb') as file_handle:
		buffer = ''
		reader = zstandard.ZstdDecompressor(max_window_size=2**31).stream_reader(file_handle)
		while True:
			chunk = read_and_decode(reader, 2**27, (2**29) * 2)

			if not chunk:
				break
			lines = (buffer + chunk).split("\n")

			for line in lines[:-1]:
				yield line, file_handle.tell()

			buffer = lines[-1]

		reader.close()


if __name__ == "__main__":
	OUT_DIR = 'FINAL PROJECT/processed'
	os.makedirs(OUT_DIR, exist_ok=True)

	#------------------------------------------------COMMENTS DATA---------------------------------------------------
	COMMENT_FILE = 'FINAL PROJECT/Reddit/reddit/comments/RC_2011-08.zst'
	file_size = os.stat(COMMENT_FILE).st_size
	file_lines = 0
	bad_lines = 0
	created = None
	comment_author = {}  # dict{comment name (t1_...) : author}, used to look up who wrote a parent comment
	comment_rows = []    # list of (author, parent_id, created_utc, subreddit)
	author_subreddits = defaultdict(list)
	text_rows = []       # list of (author, kind, subreddit, created_utc, text) for comments AND posts

	for line, file_bytes_processed in read_lines_zst(COMMENT_FILE):
		try:
			obj = json.loads(line)
			created = datetime.fromtimestamp(int(obj['created_utc']), timezone.utc)
			# sys.intern() makes repeated strings (same author/subreddit) share one copy in memory
			author = sys.intern(obj['author'])
			subreddit = sys.intern(obj['subreddit'])
			#NOTE name is the comment's id, starts with t1_
			#NOTE parent_id starts with t1_ if replying to a comment, or t3_ if replying to the post itself
			comment_author[obj['name']] = author
			comment_rows.append((author, obj['parent_id'], int(obj['created_utc']), subreddit))
			author_subreddits[author].append(subreddit)
			if obj['body'] not in ('[deleted]', '[removed]'):  # removed comments have no text left
				text_rows.append((author, 'comment', subreddit, int(obj['created_utc']), obj['body']))
		except (KeyError, json.JSONDecodeError) as err:
			bad_lines += 1
		file_lines += 1
		if file_lines % 1000000 == 0:
			log.info(f"{created.strftime('%Y-%m-%d %H:%M:%S')} : {file_lines:,} : {bad_lines:,} : {file_bytes_processed:,}:{(file_bytes_processed / file_size) * 100:.0f}%")
	log.info(f"Comments complete : {file_lines:,} : {bad_lines:,}")

	#------------------------------------------------POSTS SUBMITTED DATA------------------------------------------------
	SUBMISSION_FILE = 'FINAL PROJECT/Reddit/reddit/submissions/RS_2011-08.zst' 
	file_size = os.stat(SUBMISSION_FILE).st_size
	file_lines = 0
	bad_lines = 0  # ~1,000 promoted/ad posts have no 'author' field 
	submission_author = {}  # dict{post name (t3_...) : author}
	for line, file_bytes_processed in read_lines_zst(SUBMISSION_FILE):
		try:
			obj = json.loads(line)
			created = datetime.fromtimestamp(int(obj['created_utc']), timezone.utc)
			author = sys.intern(obj['author'])
			submission_author[obj['name']] = author
			subreddit = sys.intern(obj['subreddit'])
			author_subreddits[author].append(subreddit)
			selftext = obj.get('selftext') or ''
			if selftext in ('[deleted]', '[removed]'):
				selftext = ''
			text_rows.append((author, 'post', subreddit, int(obj['created_utc']), obj['title'] + '\n\n' + selftext))
		except (KeyError, json.JSONDecodeError) as err:
			bad_lines += 1
		file_lines += 1
		if file_lines % 1000000 == 0:
			log.info(f"{created.strftime('%Y-%m-%d %H:%M:%S')} : {file_lines:,} : {bad_lines:,} : {file_bytes_processed:,}:{(file_bytes_processed / file_size) * 100:.0f}%")
	log.info(f"Submissions complete : {file_lines:,} : {bad_lines:,}")

	#---GENEREATING A LIST OF REPLIES-------------------------(who replied, who they replied to, when, where)
	reply_edges = []
	unresolved = 0
	for author, parent_id, created_utc, subreddit in comment_rows:
		if parent_id.startswith('t1_'):
			parent_author = comment_author.get(parent_id)
		else:
			parent_author = submission_author.get(parent_id)
		if parent_author is None:  # i.e., if the comment doesn't have a parent
			unresolved += 1
			continue
		reply_edges.append((author, parent_author, created_utc, subreddit))
	log.info(f"{len(reply_edges):,} reply edges ({unresolved:,} comments had no parent.)")

	#Saving the Data:
	pickle.dump(reply_edges, open(OUT_DIR + '/reply_edges.pkl', 'wb'))
	pickle.dump(dict(author_subreddits), open(OUT_DIR + '/author_subreddits.pkl', 'wb'))

	#Dataframe for NLP:
	del comment_author, submission_author, comment_rows, reply_edges, author_subreddits
	reddit_text = pd.DataFrame(text_rows, columns=['author', 'kind', 'subreddit', 'created_utc', 'text'])
	del text_rows
	reddit_text.to_pickle(OUT_DIR + '/reddit_text.pkl')
	log.info(f"Saved reply_edges.pkl, author_subreddits.pkl and reddit_text.pkl ({len(reddit_text):,} rows) to {OUT_DIR}")
