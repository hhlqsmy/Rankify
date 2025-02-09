import torch
from rankify.models.base import BaseRanking
from rankify.dataset.dataset import Document
#from reranking.models.rank_fid import RankFiDDistill, RankFiDScore
from rankify.utils.models.rank_llm.rerank.rankllm import PromptMode
from typing import List
from rankify.utils.models.rank_llm.rerank import Reranker
from rankify.utils.models.rank_llm.data import Request
from tqdm import tqdm  # Import tqdm for progress tracking

class LiT5DistillReranker(BaseRanking):
    """
    Implements LiT5-Distill `[12]`_, a listwise reranker based on T5 encoder-decoder models.
    
    .. _[12]: https://arxiv.org/abs/2312.16098

    LiT5-Distill is designed for zero-shot ranking, leveraging sequence-to-sequence architectures
    to improve retrieval performance with efficient inference.

    References
    ----------
    .. [12] Tamber et al. (2023): Scaling Down, LiTting Up: Efficient Zero-Shot Listwise Reranking with Seq2seq Encoder-Decoder Models.

    Attributes
    ----------
    context_size : int
        The maximum number of tokens used in ranking (default: `300`).
    window_size : int
        The window size for processing candidate passages (default: `20`).
    _reranker : Reranker
        The LiT5-Distill reranking agent.

    Examples
    --------
    Basic usage:

    >>> from rankify.dataset.dataset import Document, Question, Context
    >>> from rankify.models.reranking import Reranking
    >>>
    >>> question = Question("What are the effects of climate change?")
    >>> contexts = [
    >>>     Context(text="Rising temperatures are causing ice caps to melt.", id=0),
    >>>     Context(text="Many species face extinction due to habitat loss.", id=1),
    >>>     Context(text="Ocean acidification is increasing.", id=2),
    >>> ]
    >>> document = Document(question=question, contexts=contexts)
    >>>
    >>> # Initialize LiT5-Distill reranker
    >>> model = Reranking(method='lit5distill', model_name='castorini/LiT5-Distill-base')
    >>> model.rank([document])
    >>>
    >>> # Print reordered contexts
    >>> print("Reordered Contexts:")
    >>> for context in document.reorder_contexts:
    >>>     print(context.text)
    """
    def __init__(self,method: str= None, model_name: str = "castorini/LiT5-Distill-base", api_key: str= None):
        """
        Initializes the **LiT5-Distill reranker**.

        Parameters
        ----------
        method : str, optional
            The reranking method name.
        model_name : str, optional
            The name of the pre-trained **LiT5-Distill** model (default: `"LiT5-Distill-base"`).
        api_key : str, optional
            API key for authentication (if needed).
        """
        self.context_size = 300
        self.window_size = 20
    
    
        self._reranker = Reranker(
            Reranker.create_agent(model_name, default_agent=None, interactive=False)
        )

    def rank(self, documents: List[Document]) -> List[Document]:
        """
        Reranks each document's contexts using the **LiT5-Distill model**.

        Parameters
        ----------
        documents : List[Document]
            A list of **Document** instances containing contexts to rerank.

        Returns
        -------
        List[Document]
            The reranked list of **Document** instances with updated `reorder_contexts`.
        """
        for document in tqdm(documents, desc="Reranking Documents"):
            
            document = self._rerank_document(document)
        return documents

    def _rerank_document(self, document: Document):
        """
        Reranks a **single document** using the **LiT5-Distill model**.

        Parameters
        ----------
        document : Document
            A **Document** instance containing query and contexts.

        Returns
        -------
        Document
            The document with **reranked** contexts in `reorder_contexts`.
        """
        # Prepare request data structure for reranking
        request = Request(
            query={"text": document.question.question},  # Extract `text` from `Question`
            candidates=[
                {"docid": ctx.id, "doc": {"text": ctx.text} , "score": ctx.score } for ctx in document.contexts
            ]
        )
        #print("Hello")
        rank_start= 0
        rank_end = 100
        window_size = 20
        step= 10
        shuffle_candidates = False
        logging = False,

        # Rerank using the agent
        reranked_result = self._reranker.rerank(
            request=request,
            rank_start=rank_start,
            rank_end=rank_end,
            window_size=window_size,
            step=step,
            shuffle_candidates=shuffle_candidates,
            #logging=logging,
        )
            # Create a mapping from docid to the original context
        docid_to_context = {ctx.id: ctx for ctx in document.contexts}

        # Reorder contexts based on reranked_result
        document.reorder_contexts = [
            docid_to_context[int(candidate["docid"])] for candidate in reranked_result.candidates
        ]
        return document


class LiT5ScoreReranker(BaseRanking):
    """
    Implements LiT5-Score `[12]`_, a listwise reranker that generates direct ranking scores for passages.

    .. _[12]: https://arxiv.org/abs/2312.16098

    LiT5-Score **assigns numerical scores** to **each passage** relative to a **query**, 
    allowing for **zero-shot ranking without fine-tuning**.

    References
    ----------
    .. [12] Tamber et al. (2023): Scaling Down, LiTting Up: Efficient Zero-Shot Listwise Reranking with Seq2seq Encoder-Decoder Models.


    Attributes
    ----------
    context_size : int
        The maximum number of tokens used in ranking (default: `300`).
    window_size : int
        The window size for processing candidate passages (default: `20`).
    _reranker : Reranker
        The LiT5-Score reranking agent.
    """
    def __init__(self, method: str = None, model_name: str = "castorini/LiT5-Score-base", api_key: str = None):
        """
        Initializes the **LiT5-Score reranker**.

        Parameters
        ----------
        method : str, optional
            The reranking method name.
        model_name : str, optional
            The name of the pre-trained **LiT5-Score** model (default: `"castorini/LiT5-Score-base"`).
        api_key : str, optional
            API key for authentication (if needed).
        """
        self.context_size = 300
        self.window_size = 20

        self._reranker = Reranker(
            Reranker.create_agent(model_name, default_agent=None, interactive=False)
        )

    def rank(self, documents: List[Document]) -> List[Document]:
        """
        Reranks each document's contexts using the **LiT5-Score model**.

        Parameters
        ----------
        documents : List[Document]
            A list of **Document** instances containing contexts to rerank.

        Returns
        -------
        List[Document]
            The reranked list of **Document** instances with updated `reorder_contexts`.
        """
        for document in tqdm(documents, desc="Reranking Documents"):
            document = self._rerank_document(document)
        return documents

    def _rerank_document(self, document: Document):
        """
        Reranks a **single document** using the **LiT5-Score model**.

        Parameters
        ----------
        document : Document
            A **Document** instance containing query and contexts.

        Returns
        -------
        Document
            The document with **reranked** contexts in `reorder_contexts`.
        """
        # Prepare request data structure for reranking
        request = Request(
            query={"text": document.question.question},  # Extract `text` from `Question`
            candidates=[
                {"docid": ctx.id, "doc": {"text": ctx.text}, "score": ctx.score} for ctx in document.contexts
            ]
        )

        # Reranking parameters
        rank_start = 0
        rank_end = 100
        window_size = 20
        step = 10
        shuffle_candidates = False
        logging = False

        # Rerank using the agent
        reranked_result = self._reranker.rerank(
            request=request,
            rank_start=rank_start,
            rank_end=rank_end,
            window_size=window_size,
            step=step,
            shuffle_candidates=shuffle_candidates,
            logging=logging,
        )

        # Create a mapping from docid to the original context
        docid_to_context = {ctx.id: ctx for ctx in document.contexts}

        # Reorder contexts based on reranked_result
        document.reorder_contexts = [
            docid_to_context[int(candidate["docid"])] for candidate in reranked_result.candidates
        ]
        return document

