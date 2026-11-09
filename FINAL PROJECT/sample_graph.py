import networkx as nx
import pickle
import random
from collections import defaultdictS
from tqdm import tqdm
import numpy as np
import pandas as pd

PROJECT_DIR = '/home/rh614/PythonRepos/Assignments/Assigments/FINAL PROJECT/'
OUT_DIR = PROJECT_DIR + 'processed/'

reply_edges = pickle.load(open(OUT_DIR + 'reply_edges.pkl', 'rb'))  # list[(replier, parent_author, created_utc, subreddit)]
author_subreddits = pickle.load(open(OUT_DIR + 'author_subreddits.pkl', 'rb'))  # dict{author : list(subreddit)}

#--- Sampling settings
random.seed(123)
N_SEEDS = 400  # random authors to start the snowball from (~7,000 authors total with 1 wave)
N_WAVES = 1    # how many hops out from the seeds. Everyone found is kept (no cap per person).
               # 2 waves explodes: a seed's neighbours include popular users with 1,000s of partners

# Accounts that aren't real people. '[deleted]' is many different users merged into one name,
# so it would be a fake hub. Add names here when you spot bots in the "most active" printout.
NOT_PEOPLE = {'[deleted]', 'AutoModerator', 'original-finder'}


def is_bot_or_deleted(author):
    if author in NOT_PEOPLE:
        return True
    # Crude bot filter: names ending in "bot" (e.g. haiku_robot, Gonzobot). Will catch a few humans too.
    return author.lower().endswith('bot')


def snowball_sample(reply_edges, seeds, n_waves):
    """Snowball sampling straight from the list of replies.

    Each wave scans every reply once: if one side of the reply is on the current frontier,
    the other side is someone new we add. Returns dict{author : wave they were found in}.
    """
    wave_of = {author: 0 for author in seeds}
    frontier = set(seeds)
    for wave in range(1, n_waves + 1):
        new_people = set()
        for replier, parent_author, created_utc, subreddit in tqdm(reply_edges, desc=f"wave {wave}"):
            if replier in frontier and parent_author not in wave_of:
                new_people.add(parent_author)
            elif parent_author in frontier and replier not in wave_of:
                new_people.add(replier)
        new_people = {a for a in new_people if not is_bot_or_deleted(a)}
        for author in new_people:
            wave_of[author] = wave
        frontier = new_people
        print(f"Wave {wave}: found {len(new_people)} new authors (total {len(wave_of)})")
    return wave_of


#--- Pick random seed authors (anyone who commented or posted this month) and snowball out
people = sorted(a for a in author_subreddits if not is_bot_or_deleted(a))  # sorted() so random.seed works
seeds = random.sample(people, N_SEEDS)
wave_of = snowball_sample(reply_edges, seeds, N_WAVES)
sampled_authors = set(wave_of)


#--- Build the sampled graph: ALL reply ties between sampled authors (not only the ones we walked)
# Edge weight = number of replies between the two people. We also keep every timestamped reply
# between sampled authors for the dynamics part of the project.
G = nx.Graph()
G.add_nodes_from(sampled_authors)
sample_replies = []  # list of (replier, parent_author, created_utc, subreddit)
for replier, parent_author, created_utc, subreddit in tqdm(reply_edges, desc="edges"):
    if replier in sampled_authors and parent_author in sampled_authors and replier != parent_author:
        sample_replies.append((replier, parent_author, created_utc, subreddit))
        if G.has_edge(replier, parent_author):
            G[replier][parent_author]['weight'] += 1
        else:
            G.add_edge(replier, parent_author, weight=1)

for author in G.nodes():
    G.nodes[author]['wave'] = wave_of[author]
    G.nodes[author]['n_activity'] = len(author_subreddits.get(author, []))  # comments + posts this month
# NOTE: seeds (wave 0) have ALL of their reply partners in the sample, so their degree in G is their
# true degree, and since seeds are random authors, their degrees are a fair sample of everyone's.

#Get the sub-reddit sizes by sampled authors
authors_per_sub = defaultdict(int)
for author in tqdm(sampled_authors):
    for sub in set(author_subreddits.get(author, [])):  #set() to Remove duplicates
        authors_per_sub[sub] += 1


N = G.number_of_nodes()
L = G.number_of_edges()
deg = dict(G.degree())
k_avg = np.mean(list(deg.values()))

print("N: ", N)
print("L: ", L)
print("Average Degree: ", k_avg)
print("Average Degree of seeds (their true degree): ", np.mean([deg[a] for a in seeds]))
print("Seeds with no replies at all: ", sum(1 for a in seeds if deg[a] == 0))
print("Connected components: ", nx.number_connected_components(G))


pickle.dump(G, open(OUT_DIR + 'G.pkl', 'wb'))
pickle.dump(dict(authors_per_sub), open(OUT_DIR + 'authors_per_sub.pkl', 'wb'))
#Save the timestamped replies as a DataFrame: easy to slice by week later for the dynamics part
sample_replies = pd.DataFrame(sample_replies, columns=['replier', 'parent_author', 'created_utc', 'subreddit'])
sample_replies['time'] = pd.to_datetime(sample_replies['created_utc'], unit='s')
sample_replies.to_pickle(OUT_DIR + 'sample_replies.pkl')
