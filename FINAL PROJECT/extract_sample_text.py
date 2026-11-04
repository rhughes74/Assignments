# Label sampled authors as Depressed / Not Depressed from the words they use.
# Run after load_raw_reddit_data.py and sample_graph.py (re-uses reddit_text.pkl, no re-parsing of raw files).
#
# Idea: count how often each author uses words/phrases tied to the WHO's symptoms of a depressive episode
# (ICD-10 F32: depressed mood, loss of interest, low energy, poor concentration, low self-worth, guilt,
# hopelessness, self-harm/suicidal thoughts, sleep and appetite changes). Authors whose rate (per 1,000
# words) is in the top few percent are labelled Depressed.
# Inspiration: Vedula & Parthasarathy (2017), Emotional and Linguistic Cues of Depression from Social Media.
#
# Saves:
#   processed/author_labels.pkl  DataFrame, one row per sampled author: n_words, n_hits, rate, depressed
#   processed/author_weeks.pkl   DataFrame, one row per (author, week): n_words, n_hits  (for dynamics)
#   processed/G_labeled.pkl      G.pkl plus 'depressed' and 'depression_rate' node attributes
import re
import pickle
import numpy as np
import pandas as pd
import networkx as nx

PROJECT_DIR = '/home/rh614/PythonRepos/Assignments/Assigments/FINAL PROJECT/'
OUT_DIR = PROJECT_DIR + 'processed/'

MIN_WORDS = 200              # too little text = can't judge; these authors get depressed = None
DEPRESSED_PERCENTILE = 95    # top 5% of depression-word rates are labelled Depressed
AUG_1_2011 = 1312156800      # Monday 2011-08-01 00:00 UTC, used to number the weeks 0..4

# Words/phrases grouped by WHO (ICD-10) depressive-episode symptom. An apostrophe is optional when
# matching ("can't" also matches "cant"), and a space also matches a hyphen ("self harm" = "self-harm").
WHO_DEPRESSION_WORDS = {
    'depressed mood':      ['depressed', 'depression', 'hopeless', 'miserable', 'feel empty', 'so sad',
                            'feel sad', 'feeling sad', 'crying', 'cried myself'],
    'loss of interest':    ['lost interest', 'no interest in', "don't enjoy", "can't enjoy", 'nothing matters',
                            'no motivation', 'numb'],
    'low energy':          ['exhausted', 'no energy', 'tired all the time', 'always tired', 'drained', 'fatigue'],
    'poor concentration':  ["can't concentrate", "can't focus", "can't think straight"],
    'low self-worth':      ['worthless', 'hate myself', "i'm a failure", "i'm useless", "i'm a burden", 'self loathing'],
    'guilt':               ['guilty', 'my fault', 'ashamed'],
    'hopelessness':        ['no future', 'give up', "what's the point", 'no reason to live'],
    'self-harm / suicide': ['suicide', 'suicidal', 'kill myself', 'want to die', 'end it all', 'self harm',
                            'cutting myself'],
    'sleep problems':      ['insomnia', "can't sleep", 'sleep all day'],
    'appetite changes':    ['no appetite', 'lost my appetite', 'stopped eating'],
}


def phrase_to_regex(phrase):
    pattern = re.escape(phrase)
    pattern = pattern.replace("'", "'?")      # apostrophe optional
    pattern = pattern.replace("\\ ", "[\\s-]")  # space or hyphen
    return pattern

all_phrases = [p for phrases in WHO_DEPRESSION_WORDS.values() for p in phrases]
DEPRESSION_REGEX = r"\b(?:" + "|".join(phrase_to_regex(p) for p in all_phrases) + r")\b"


#--- Load and keep only sampled authors
G = pickle.load(open(OUT_DIR + 'G.pkl', 'rb'))
reddit_text = pd.read_pickle(OUT_DIR + 'reddit_text.pkl')
text = reddit_text[reddit_text['author'].isin(set(G.nodes()))].copy()
del reddit_text  # free memory
print("Comments/posts by sampled authors:", len(text))

#--- Count words and depression-word hits in every comment/post
text['n_words'] = text['text'].str.count(r'\S+')
text['n_hits'] = text['text'].str.count(DEPRESSION_REGEX, flags=re.IGNORECASE)
text['week'] = (text['created_utc'] - AUG_1_2011) // (7 * 24 * 3600)  # week 4 is only Aug 29-31

#--- Per author: get the rate per 1,000 words, then  label the top 5% as depressed
author_labels = text.groupby('author')[['n_words', 'n_hits']].sum()
author_labels['rate'] = 1000 * author_labels['n_hits'] / author_labels['n_words'].clip(lower=1)
enough_text = author_labels['n_words'] >= MIN_WORDS
threshold = np.percentile(author_labels.loc[enough_text, 'rate'], DEPRESSED_PERCENTILE)
author_labels['depressed'] = None
author_labels.loc[enough_text, 'depressed'] = author_labels.loc[enough_text, 'rate'] >= threshold

print(f"Authors with >= {MIN_WORDS} words: {enough_text.sum()} of {G.number_of_nodes()}")
print(f"Depressed threshold: {threshold:.2f} depression words per 1,000 words")
print("Labelled Depressed:", (author_labels['depressed'] == True).sum())

#---Words Depressed vs Non-Depressed, per week
author_weeks = text.groupby(['author', 'week'])[['n_words', 'n_hits']].sum().reset_index()

#Save
author_labels.to_pickle(OUT_DIR + 'author_labels.pkl')
author_weeks.to_pickle(OUT_DIR + 'author_weeks.pkl')

# Dictionaries of {author : value}. (The index of author_labels is the author name, so .to_dict() on a
# column gives {node : value} dict that nx.set_node_attributes() requires.)
depressed_dict = author_labels['depressed'].to_dict()
rate_dict = author_labels['rate'].to_dict()

#Align depressed data against 'G'
depressed_dict = {author: depressed_dict.get(author) for author in G.nodes()}
rate_dict = {author: rate_dict.get(author) for author in G.nodes()}

nx.set_node_attributes(G, depressed_dict, 'depressed')
nx.set_node_attributes(G, rate_dict, 'depression_rate')

depressed_nodes = [n for n, d in G.nodes(data='depressed') if d == True]
not_depressed_nodes = [n for n, d in G.nodes(data='depressed') if d == False]
print("Depressed nodes:", len(depressed_nodes), "| Not depressed nodes:", len(not_depressed_nodes))


#Save
pickle.dump(G, open(OUT_DIR + 'G_labeled.pkl', 'wb'))
