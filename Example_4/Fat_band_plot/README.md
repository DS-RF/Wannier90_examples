
# Plot fat bands for Mo d orbitals

To run this example, it is necessary to use pseudopotentials that contain the atomic wave functions required for orbital projections.

Run QE calculations:

> pw.x < scf.in  > scf.out

> pw.x < bands.in > bands.out

> bands.x < bandsx.in > bandsx.out

> projwfc.x < projwfc.in > projwfc.out

Then run Python script

> python3 read_fatbands.py projwfc.out --eref -0.9612 -o fatbands.dat

Here -0.9612 is the VBM level, which can be found in *scf.out*.

Plot the results 

> gnuplot plot_fat_bands_z2_xy_x2_y2.gnu

![GitHub Logo](fat_bands_dxy_x2y2_z2_purple.png) 
