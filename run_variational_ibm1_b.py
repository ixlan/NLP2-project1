import numpy as np
from models.variational_ibm1_b import VariationalIBM1
from misc.vocabulary import Vocabulary
from misc.utils import tokenize_corpora_to_ids
from misc.support import log_info
from aer import read_naacl_alignments, AERSufficientStatistics

def calculate_aer(predictions):
    from random import random
    # 1. Read in gold alignments
    gold_sets = read_naacl_alignments('data/validation/dev.wa.nonullalign')

    # 3. Compute AER
    metric = AERSufficientStatistics()
    for gold, pred in zip(gold_sets, predictions):
        metric.update(sure=gold[0], probable=gold[1], predicted=pred)
    return metric.aer()

def save_params(model, to_file):
    log_info("Saving parameters to %s" % to_file)
    with open(to_file, "w+") as f:
        np.save(f, model.p_f_given_e)

def load_params(model, from_file):
    log_info("Loading parameters from %s" % from_file)
    params = np.load(from_file)
    model.p_f_given_e = params

# Model hyperparameters
num_iterations = 10
max_vocab_size = 500
min_count = 5
small_dataset = True
alpha = 1e-4

# Data files.
french_file_path = "data/training/small/hansards.36.2.f" if small_dataset else "data/training/hansards.36.2.f"
french_validation_file_path = "data/validation/dev.f"
english_file_path = "data/training/small/hansards.36.2.e" if small_dataset else "data/training/hansards.36.2.e"
french_validation_file_path = "data/validation/dev.f"
english_validation_file_path = "data/validation/dev.e"
french_vocab_path = "data/vocabulary/french.txt"
english_vocab_path = "data/vocabulary/english.txt"

# Load the vocabularies for English and French.
vocab_french = Vocabulary(french_file_path, vocab_file_path=french_vocab_path, min_count=min_count, \
        max_size=max_vocab_size)
vocab_english = Vocabulary(english_file_path, vocab_file_path=english_vocab_path, min_count=min_count, \
        max_size=max_vocab_size)

# Set up the model.
log_info("Setting up the model, French vocabulary size = %d, English vocabulary size = %d, alpha=%f." % \
        (len(vocab_french), len(vocab_english), alpha))
model = VariationalIBM1(french_vocab_size=len(vocab_french), english_vocab_size=len(vocab_english), alpha=alpha)
log_info("Model has been set up.")

# Tokenize the French and English sentences.
parallel_corpus = tokenize_corpora_to_ids(vocab_french, vocab_english, \
        french_file_path=french_file_path, english_file_path=english_file_path)
parallel_validation_corpus = tokenize_corpora_to_ids(vocab_french, vocab_english, \
        french_file_path=french_validation_file_path, english_file_path=english_validation_file_path)

# Calculate the validation AER and log likelihood for the initial parameters.
predictions = []
for french_sentence, english_sentence in parallel_validation_corpus:
    alignments = model.align(french_sentence, english_sentence)

    # Remove null alignments from predictions
    filtered_alignments = [al for al in alignments if al[0] != 0]

    predictions.append(set(filtered_alignments))
aer = calculate_aer(predictions)
val_elbo = 0 #model.ELBO(parallel_validation_corpus)
elbo = model.ELBO(parallel_corpus)
log_info("Iteration %2d/%d: ELBO = %.4f, val_ELBO = %.4f, validation_AER = %.4f" % \
        (0, num_iterations, elbo, val_elbo, aer))

# Train the model for num_iterations EM steps.
log_info("Start training model.")
for it_num in range(1, num_iterations + 1):
    model.train(parallel_corpus)

    # Calculate the validation AER
    predictions = []
    for french_sentence, english_sentence in parallel_validation_corpus:
        alignments = model.align(french_sentence, english_sentence)
        predictions.append(set(alignments))
    aer = calculate_aer(predictions)

    val_elbo = 0 #model.ELBO(parallel_validation_corpus)
    elbo = model.ELBO(parallel_corpus)
    log_info("Iteration %2d/%d: ELBO = %.4f, val_ELBO = %.4f, validation_AER = %.4f" % \
            (it_num, num_iterations, elbo, val_elbo, aer))
# save_params(model, "params/final_params_ibm1_%d_it.npy" % num_iterations)

log_info("Done training model.")
