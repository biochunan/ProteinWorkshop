create_conda_env:
	conda create -n proteinworkshop python=3.10 -y

install_dependencies:
	pip install -e .
	@echo "Install PyTorch with CUDA 11.8 support on Linux:"
	pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 torchaudio==2.1.2+cu118 --index-url https://download.pytorch.org/whl/cu118
	@echo "use the newly-installed proteinworkshop CLI to install pytorch geometric"
	workshop install pyg
	@echo "Install other dependencies"
	pip install torch_scatter torch_sparse torch_cluster torch_spline_conv -f https://data.pyg.org/whl/torch-2.1.2+cu118.html
	pip install gdown>=5.1.0
	@echo "Clearing cache"
	pip cache purge && conda clean -a -y

download_data:
	# python proteinworkshop/scripts/download_pdb_bcif.py
	workshop download pdb