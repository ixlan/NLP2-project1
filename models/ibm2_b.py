import numpy as np
from time import gmtime, strftime, time

# TODO temp
def log_info(log_string):
    time_string = strftime("%H:%M:%S", gmtime())
    print("%s [INFO]: %s" % (time_string, log_string))

class IBM2():

    def __init__(self, french_vocab_size, english_vocab_size, max_jump=10, init="uniform"):
        self.num_allowed_jumps = 2 * max_jump + 1
        self.expected_lexical_counts = np.zeros((french_vocab_size, english_vocab_size))
        self.expected_jump_counts = np.zeros(self.num_allowed_jumps)
        self.expected_null_jump_count = 0.

        # Initialize parameters uniformly. We have no prior knowledge. Note that these parameters
        # are not random and therefore EM will run deterministically.
        if init == "uniform":
            log_info("Initializing parameters uniformly")
            self.p_f_given_e = np.full((french_vocab_size, english_vocab_size), 1.0 / french_vocab_size)
            self.jump_p = np.full(self.num_allowed_jumps, 1.0 / (self.num_allowed_jumps + 1.))
            self.null_jump_p = 1.0 / (self.num_allowed_jumps + 1.)
        elif init == "random":
            log_info("Initializing parameters randomly")
            self.p_f_given_e = np.exp(np.random.normal(loc=0., scale=1., size=(french_vocab_size, english_vocab_size)))
            self.p_f_given_e = self.p_f_given_e / (np.sum(self.p_f_given_e, \
                    axis=0, keepdims=True))
            self.jump_p = np.exp(np.random.normal(loc=0., scale=1., size=self.num_allowed_jumps))
            self.null_jump_p = np.exp(np.random.normal(loc=0., scale=1., size=1))
            Z = np.sum(self.jump_p) + self.null_jump_p
            self.jump_p /= Z
            self.null_jump_p /= Z
        elif init == "ibm1":
            self.jump_p = np.full(self.num_allowed_jumps, 1.0 / (self.num_allowed_jumps + 1.))
            self.null_jump_p = 1.0 / (self.num_allowed_jumps + 1.)
        else:
            log_info("Unknown initialization method.")

        self.max_jump = max_jump
        self.epsilon = 1e-6

    # Performs a single E and M step over the entire given dataset.
    def train(self, parallel_corpus):

        # Make sure the expected counts matrices contain only zeros.
        self.expected_lexical_counts.fill(0.)
        self.expected_jump_counts.fill(0.)
        self.expected_null_jump_count = 0.

        # Perform the expectation (E) step using the current parameters.
        for (french_sentence, english_sentence) in parallel_corpus:

            for j, f_j in enumerate(french_sentence):

                # Compute the posterior probabilities for each possible alignment for this french word.
                posterior_probs = np.zeros(len(english_sentence))
                deltas = np.zeros(len(english_sentence), dtype=int)
                for i, e_i in enumerate(english_sentence):
                    delta = self.delta(j, i, len(french_sentence), len(english_sentence))
                    alignment_prob = self.jump_prob(delta, i)
                    posterior_probs[i] = alignment_prob * self.p_f_given_e[f_j, e_i]
                    deltas[i] = delta
                posterior_probs /= (np.sum(posterior_probs) + self.epsilon)

                # Compute the expected counts.
                for i, e_i in enumerate(english_sentence):

                    # Consider the case that f_j was generated from e_i. Add to the expected count of this event
                    # occurring, weighted by the posterior probability.
                    self.expected_lexical_counts[f_j, e_i] += posterior_probs[i]
                    if i != 0:
                        self.expected_jump_counts[self.jump_p_index(deltas[i])] += posterior_probs[i]
                    else:
                        self.expected_null_jump_count += posterior_probs[i]

        # Perform the maximization (M) step to update the parameters.
        self.p_f_given_e = self.expected_lexical_counts / (np.sum(self.expected_lexical_counts, \
                axis=0, keepdims=True) + self.epsilon)
        Z = np.sum(self.expected_jump_counts) + self.expected_null_jump_count + self.epsilon
        self.jump_p = self.expected_jump_counts / Z
        self.null_jump_p = self.expected_null_jump_count / Z

    # Computes the marginal log likelihood.
    def compute_log_likelihood(self, parallel_corpus):
        ll = 0.
        num_data_points = 0
        for (french_sentence, english_sentence) in parallel_corpus:
            num_data_points += 1
            for j, f_j in enumerate(french_sentence):
                inner_sum = 0.
                for i, e_i in enumerate(english_sentence):
                    delta = self.delta(j, i, len(french_sentence), len(english_sentence))
                    p_alignment = self.jump_prob(delta, i)
                    inner_sum += p_alignment * self.p_f_given_e[f_j, e_i]
                ll += np.log(inner_sum + 1e-10)

        return ll / num_data_points

    # Returns the jump probability of a given delta.
    def jump_prob(self, delta, i):
        if i == 0:
            return self.null_jump_p
        else:
            return 0. if np.abs(delta) > self.max_jump else self.jump_p[self.jump_p_index(delta)]

    # Returns the index in the jump_p array of the given delta. Only works for valid values of delta given the
    # max_jump setting.
    def jump_p_index(self, delta):
        return (self.max_jump * 2 - delta) % self.num_allowed_jumps

    # Calculates the delta for a tuple (j, i, n, m).
    def delta(self, french_pos, eng_pos, french_len, eng_len):
        return int(eng_pos - np.floor(french_pos * (float(eng_len) / french_len)))

    # Given a French and English sentence, return the Viterbi alignment, i.e. the alignment with the maximum
    # posterior probability.
    def infer_alignment(self, french_sentence, english_sentence):
        alignment = np.zeros(len(french_sentence), dtype=int)

        # Note that we can pick the best alignment individually for each French word, since the individual alignments
        # are assumed to be independent from each other in our model.
        for j, f_j in enumerate(french_sentence):
            posterior_probs = np.zeros(len(english_sentence))
            for i, e_i in enumerate(english_sentence):
                delta = self.delta(j, i, len(french_sentence), len(english_sentence))
                alignment_prob = self.jump_prob(delta, i)
                posterior_probs[i] = alignment_prob * self.p_f_given_e[f_j, e_i]
            posterior_probs /= (np.sum(posterior_probs) + self.epsilon)
            alignment[j] = np.argmax(posterior_probs)

        return alignment
