from typing import Set, Union

import e3nn
import torch
import torch.nn.functional as F
from beartype import beartype
from graphein.protein.tensor.data import ProteinBatch
from jaxtyping import jaxtyped
from torch_geometric.data import Batch

import src.models.graph_encoders.layers.tfn as tfn
from src.models.graph_encoders.components import blocks
from src.models.utils import get_aggregation
from src.types import EncoderOutput


class TensorProductModel(torch.nn.Module):
    def __init__(
        self,
        r_max: float = 10.0,
        num_bessel: int = 8,
        num_polynomial_cutoff: int = 5,
        max_ell: int = 2,
        num_layers: int = 4,
        emb_dim: int = 64,
        mlp_dim: int = 256,
        aggr: str = "sum",
        pool: str = "sum",
        residual: bool = True,
        batch_norm: bool = True,
        gate: bool = False,
        hidden_irreps=None,
    ):
        super().__init__()
        self.r_max = r_max
        self.max_ell = max_ell
        self.num_layers = num_layers
        self.emb_dim = emb_dim
        self.mlp_dim = mlp_dim
        self.residual = residual
        self.batch_norm = batch_norm
        self.gate = gate
        self.hidden_irreps = hidden_irreps

        # Edge embedding
        self.radial_embedding = blocks.RadialEmbeddingBlock(
            r_max=r_max,
            num_bessel=num_bessel,
            num_polynomial_cutoff=num_polynomial_cutoff,
        )
        sh_irreps = e3nn.o3.Irreps.spherical_harmonics(max_ell)
        self.spherical_harmonics = e3nn.o3.SphericalHarmonics(
            sh_irreps, normalize=True, normalization="component"
        )

        # Embedding lookup for initial node features
        self.emb_in = torch.nn.LazyLinear(emb_dim)

        # Set hidden irreps if none are provided
        if hidden_irreps is None:
            hidden_irreps = (sh_irreps * emb_dim).sort()[0].simplify()
            # Note: This defaults to O(3) equivariant layers
            # It is possible to use SO(3) equivariance by passing the appropriate irreps

        self.convs = torch.nn.ModuleList()
        # First conv layer: scalar only -> tensor
        self.convs.append(
            tfn.TensorProductConvLayer(
                in_irreps=e3nn.o3.Irreps(f'{emb_dim}x0e'),
                out_irreps=hidden_irreps,
                sh_irreps=sh_irreps,
                edge_feats_dim=self.radial_embedding.out_dim,
                mlp_dim=mlp_dim,
                aggr=aggr,
                batch_norm=batch_norm,
                gate=gate,
            )
        )
        # Intermediate conv layers: tensor -> tensor
        for _ in range(num_layers - 2):
            conv = tfn.TensorProductConvLayer(
                in_irreps=hidden_irreps,
                out_irreps=hidden_irreps,
                sh_irreps=sh_irreps,
                edge_feats_dim=self.radial_embedding.out_dim,
                mlp_dim=mlp_dim,
                aggr=aggr,
                batch_norm=batch_norm,
                gate=gate,
            )
            self.convs.append(conv)
        # Last conv layer: tensor -> scalar only
        self.convs.append(
            tfn.TensorProductConvLayer(
                in_irreps=hidden_irreps,
                out_irreps=e3nn.o3.Irreps(f'{emb_dim}x0e'),
                sh_irreps=sh_irreps,
                edge_feats_dim=self.radial_embedding.out_dim,
                mlp_dim=mlp_dim,
                aggr=aggr,
                batch_norm=batch_norm,
                gate=gate,
            )
        )

        # Global pooling/readout function
        self.readout = get_aggregation(pool)

    @property
    def required_batch_attributes(self) -> Set[str]:
        return {"edge_index", "pos", "x", "batch"}

    @jaxtyped
    @beartype
    def forward(self, batch: Union[Batch, ProteinBatch]) -> EncoderOutput:
        # Node embedding
        h = self.emb_in(batch.x)  # (n,) -> (n, d)

        # Edge features
        vectors = (
            batch.pos[batch.edge_index[0]] - batch.pos[batch.edge_index[1]]
        )  # [n_edges, 3]
        lengths = torch.linalg.norm(vectors, dim=-1, keepdim=True)  # [n_edges, 1]
        edge_attrs = self.spherical_harmonics(vectors)
        edge_feats = self.radial_embedding(lengths)

        for conv in self.convs:
            # Message passing layer
            h_update = conv(h, batch.edge_index, edge_attrs, edge_feats)
            # TODO it may be useful to concatenate node scalar type l=0 features 
            # from both src and dst nodes into edge_feats (RBF of displacement), as in
            # https://github.com/gcorso/DiffDock/blob/main/models/score_model.py#L263

            # Update node features
            h = h_update + F.pad(h, (0, h_update.shape[-1] - h.shape[-1])) if self.residual else h_update

        return EncoderOutput({
            "node_embedding": h,
            "graph_embedding": self.readout(h, batch.batch),  # (n, d) -> (batch_size, d)
        })


if __name__ == "__main__":
    import hydra
    import omegaconf

    from src import constants

    cfg = omegaconf.OmegaConf.load(constants.PROJECT_PATH / "configs" / "encoder" / "tfn.yaml")
    enc = hydra.utils.instantiate(cfg)
    print(enc)