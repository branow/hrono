# UMAP recipe (n_components=25, metric=cosine, seed=42) vs input size

| N vectors | outcome |
| --- | --- |
| 5 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 7 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 10 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 15 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 20 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 25 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 26 | TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.t |
| 27 | ok -> shape (27, 25) |
| 28 | ok -> shape (28, 25) |
| 30 | ok -> shape (30, 25) |
| 40 | ok -> shape (40, 25) |
