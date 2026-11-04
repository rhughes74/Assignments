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

#Discover the authors for each sampled post
by_post = defaultdict(list)
for comment, inner_dict in tqdm(all_comments.items()):
    for author, post in inner_dict.items():
        if post in sampled_posts:
            by_post[post].append(author) #This still introduces bias, because posts tend to have multiple commenters,
            # and we miss out on those who don't comment
            # Further, posts with no comments may all appear as a single node right?

#OLD: Allows us to show a graph of connected comments
#for cid, pid in all_comments.items():
#    if pid in sampled_posts:
#        by_post[pid].append(cid)

#Add edges for each pair of authors that commented on the same post
G = nx.Graph()
for pid, authors in tqdm(by_post.items()):
    if not authors: #Exclude posts with no comments
        pass                         
    else:
        authors = set(authors) #Remove duplicates
        if '[deleted]' in authors: #Exclude commenters that have '[deleted]' their accounts. 
            authors.remove('[deleted]') # is it possible to id '[deleted]' users? Could be worthwhile. do i just give them a random id though?
            G.add_edges_from(combinations(authors, 2))
        else:
            G.add_edges_from(combinations(authors, 2))

# Is this okay/correct? 
# or am I artificially creating connections by assuming all comments on the same post are connected?
# how can a comment be unconnected? 
# Should the graph reflect posts? or be bi-partite? i.e., posts to comments? posts-to-posts? or comments-to-comments?
# could definitely try and show both projections
#I really ought to use user_id, but connect based upon link_id

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