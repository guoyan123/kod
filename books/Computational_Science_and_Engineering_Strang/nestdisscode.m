%7.1  nestdisscode.m

N = 7; K = delsq(numgrid('S',N+2)); % 5-point matrix K2D on N by N grid
perm = nestdiss(N,N);               % order nodes by nested dissection
NZ = nnz(chol(K(perm,perm)))        % count nonzeros in triangular factor
fill = NZ-nnz(tril(K))              % count fill in triangular factor

function perm = nestdiss(m,n)   % perm(k) = old number of new node k
map = recur(m,n);               % map(i,j) = new number of old node
perm(map(:)) = 1:m*n;           % perm is the inverse of map

function map = recur(m,n)       % start with mn nodes numbered by rows
map = zeros(m,n);               % initialize node map
if m == 0 | n == 0, return; end % stop when mesh is fully dissected
if m >= n, r = round((m+1)/2);  % split longer side of the rectangle
  P = recur(r-1,n);             % recursively dissect the first r-1
  Q = recur(m-r,n);             % recursively dissect the last m-r
  map(1:r-1,:) = P;             % nodes of P keep current numbers
  map(r+1:m,:) = (r-1)*n+Q;     % nodes of Q are numbered next
  map(r,:) = (m-1)*n+(1:n);     % nodes of S are numbered last
else
  map = recur(n,m)'; end        % if m < n work with the transpose
