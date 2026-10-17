# Public spot capture + operational candidates

Raw candle count: 15000. Candidate count: 110. Labels: {'CONTINUE': 1, 'HALT': 106, 'REVIEW': 3}.

Only public live-market data. Private account data absent. Numeric market facts are captured evidence; policy outcomes are derived candidate labels, not human-reviewed gold. Synthetic perturbations are marked in candidate_metadata.csv. The capture is one unsplit provenance group. The existing held-out test and challenge datasets remain untouched. Human annotation, broader supported-symbol policy and independent time/source-group split review are required before training. Do not train directly on raw OHLCV as operational-state ground truth. Shadow model predictions must not become training labels.
