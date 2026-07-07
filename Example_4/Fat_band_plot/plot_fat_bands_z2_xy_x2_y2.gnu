set terminal pngcairo size 600,600
set output 'fat_bands_dxy_x2y2_z2.png'

#     3:dz2 4:dxz 5:dyz 6:dx2-y2 7:dxy

set yrange [ -6 :  5]
set xrange [  0 :  1.5774]

set xtics ("{/Symbol G}"  0.00000,\
           "M"  0.5774, \
           "K"  0.9107, \
           "{/Symbol G}"  1.5774) # taken from bands.out.gnu corresponding to M, K, and G points 

set arrow from 0.5774, graph 0 to 0.5774, graph 1 nohead
set arrow from 0.9107, graph 0 to 0.9107, graph 1 nohead

set label 'd_{{z}^{2}}+d_{{xy}}+d_{{x}^{2}-{y}^{2}}' at screen 0.92,0.65 right font 'Times-Roman-Italic, 22'

plot 'fatbands.dat' using 1:2:(5*($3+$6+$7)) with points pt 7 ps variable lc rgb "purple" notitle, \
     'fatbands.dat' using 1:2 with lines lw 2 notitle

