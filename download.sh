set -ex

mkdir -p pdfs
pushd pdfs

for i in `seq 2004 2018`
do
  wget -nc -O "radfahrer$i.pdf" "https://www.berlin.de/polizei/_assets/aufgaben/anlagen-verkehrssicherheit/radfahrer$i.pdf" || true
done

for i in `seq 2004 2009`
do
  wget -nc -O "radfahrer$i.pdf" "https://www.berlin.de/polizei/_assets/aufgaben/anlagen-verkehrssicherheit/radfahrer_$i.pdf" || true
done

wget -nc -O radfahrer2003.pdf "https://www.berlin.de/polizei/_assets/aufgaben/anlagen-verkehrssicherheit/verkehrsunfallageradfahrer2003.pdf" || true
popd
