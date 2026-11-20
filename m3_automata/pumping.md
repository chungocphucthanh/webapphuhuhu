# Pumping lemma for exact balance

This note proves requirement 3.4(b): the language of equal morning and afternoon counts over $\Sigma=\lbrace M,A,N,\texttt{-}\rbrace$ is not regular. It supports [3.4](3.4.md).

## Statement

Let $L=\lbrace w\in\Sigma^{\ast}: \#_ M(w)=\#_ A(w)\rbrace$, where $\#_ a(w)$ counts the occurrences of $a$ in $w$. Then $L$ is not regular.

## Reduction

$R=M^{\ast}A^{\ast}$ is regular. Regular languages are closed under intersection, so if $L$ were regular then

$$L'=L\cap R=\lbrace M^nA^n: n\geq 0\rbrace$$

would be regular. A word of $R$ has the form $M^iA^j$ and lies in $L$ exactly when $i=j$, which gives the equality above. It remains to show that $L'$ is not regular.

## Pumping argument

Suppose $L'$ is regular with pumping length $p\geq 1$. The word $s=M^pA^p$ is in $L'$ and $|s|\geq p$, so $s=xyz$ with $|xy|\leq p$, $|y|\geq 1$ and $xy^iz\in L'$ for all $i\geq 0$.

Since $|xy|\leq p$, both $x$ and $y$ lie inside the block $M^p$, so $y=M^k$ with $1\leq k\leq p$. For $i=0$,

$$xz=M^{p-k}A^p.$$

It has $\#_ M(xz)=p-k<p=\#_ A(xz)$ because $k\geq 1$, so $xz\notin L'$. This contradicts the third condition of the lemma. Hence $L'$ is not regular, and by the reduction neither is $L$.

## Small example

For $p=3$, $s=\texttt{MMMAAA}$. Any split with $|xy|\leq 3$ and $y\neq\varepsilon$ puts $y$ inside `MMM`. For $x=\varepsilon$, $y=\texttt{M}$ the word $xy^0z=\texttt{MMAAA}$ has 2 morning and 3 afternoon symbols, so it is not in $L'$.

## Limits

The proof is for the exact count over words of unbounded length. For a fixed horizon $T$ the set of words of length $T$ with $\#_ M=\#_ A$ is finite, hence regular, but its automaton has $O(T)$ states and changes with $T$; the bounded rule R4 of 3.4 is the fixed-size alternative.
