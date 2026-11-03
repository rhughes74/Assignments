import networkx as nx
import pickle
from itertools import combinations
from collections import defaultdict
import matplotlib.pyplot as plt
from tqdm import tqdm 
import numpy as np

all_comments = pickle.load(open('/home/rh614/PythonRepos/Assignments/Assigments/all_comments.pkl', 'rb'))# dict{comment : post} 
all_posts = pickle.load(open('/home/rh614/PythonRepos/Assignments/Assigments/all_submissions.pkl', 'rb'))# list[post]

#print(all_comments)
#print(all_posts)


#if submissions.name == comments.link_id then the comment appeared on the post
np.random.seed(123)
sampled_posts = set(np.random.choice(all_posts, size=1000))

by_post = defaultdict(list)
for cid, pid in all_comments.items():
    if pid in sampled_posts:
        by_post[pid].append(cid)

MAX_COMMENTS = 50 #Is this okay/correct? or artificially deflating my degree distribution?
G = nx.Graph()
for pid, cids in tqdm(by_post.items()):
    MAX_COMMENTS = len(cids) #setting no limit 
    if len(cids) > MAX_COMMENTS:
        cids = np.random.choice(cids, size=MAX_COMMENTS)
    G.add_edges_from(combinations(cids, 2))

N= G.number_of_nodes()
L= G.number_of_edges()
deg = dict(G.degree())
cc = list(dict(nx.clustering(G)).values())

k_avg= np.mean(list(deg.values()))
average_clustering = np.mean(cc)

print("N: ", N)
print("L: ", L)
print("Average Degree: ", k_avg)
print("Average Clustering: ", average_clustering)

pickle.dump(G, open('G.pkl', 'wb'))#Save the data to a pkl