mkdir nspv
mkdir nspv/win64
mkdir nspv/linux64
mkdir nspv/osx
cd nspv/win64
wget https://github.com/pbca26/libnspv/releases/download/v0.3.1/nspv-win.tar
tar -xvf nspv-win.tar
rm nspv-win.tar
cd ../linux64
wget https://github.com/pbca26/libnspv/releases/download/v0.3.1/nspv-linux.tar
tar -xvf nspv-linux.tar
rm nspv-linux.tar
cd ../osx
wget https://github.com/pbca26/libnspv/releases/download/v0.3.1/nspv-osx.tar
tar -xvf nspv-osx.tar
rm nspv-osx.tar
