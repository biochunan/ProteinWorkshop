#!/bin/zsh

# set -e

# init conda
conda init zsh

# source .zshrc to activate conda
source $HOME/.zshrc

# turn off conda auto-activate base
conda config --set auto_activate_base false

# set work dir
conda create -n proteinworkshop python=3.10 -y
conda env update -f $HOME/environment.yaml

# cleanup
conda clean -a -y && \
pip cache purge && \
sudo apt autoremove -y
