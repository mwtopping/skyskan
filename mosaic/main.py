import time
from glob import glob
import matplotlib.pyplot as plt
from sklearn.neighbors import KDTree
from tqdm import tqdm
import itertools
import numpy as np
import cv2 as cv

from find_stars import *

from astropy.visualization import ZScaleInterval


def get_total_shift_inv(shift):

    tot_shift_h = [0, 0]
    tot_shift_v = [0, 0]
    if shift[0]>shift[1]:
        tot_shift_v = [0, shift[0]-shift[1]]
    else:
        tot_shift_v = [shift[1]-shift[0], 0]

    if shift[2]>shift[3]:
        tot_shift_h = [0, shift[2]-shift[3]]
    else:
        tot_shift_h = [shift[3]-shift[2], 0]


    return [tot_shift_v[0], tot_shift_v[1],
            tot_shift_h[0], tot_shift_h[1]]

# currently unused
def transform_points(rot, shift, points, recenter=False):

    if recenter:
        mean = np.mean(points, axis=0)
        points -= mean
    else:
        mean = 0


    ones = np.ones(np.shape(points)[0])
    points = np.column_stack((points, ones))

    rotmat = np.matrix([[np.cos(rot),-1*np.sin(rot), shift[0]],
                        [np.sin(rot),np.cos(rot), shift[1]],
                        [0,0,1]])
    outpoints = (rotmat*points.T).T[:,:2]
    if recenter:
        outpoints += mean
    return outpoints 



def get_angles(xs, ys):

    a = np.sqrt((xs[0]-xs[1])**2 + (ys[0]-ys[1])**2)
    b = np.sqrt((xs[1]-xs[2])**2 + (ys[1]-ys[2])**2)
    c = np.sqrt((xs[0]-xs[2])**2 + (ys[0]-ys[2])**2)
    
    a1 = np.arccos((a*a + c*c - b*b) / (2*a*c))#opposite point 0
    a2 = np.arccos((a*a + b*b - c*c) / (2*a*b))#opposite point 1
    a3 = np.arccos((b*b + c*c - a*a) / (2*b*c))#opposite point 2

    angles = np.array([a1, a2, a3])
    sorted_inds = np.argsort(angles)
    sorted_angles = angles[sorted_inds]
    sorted_pos = [xs[sorted_inds], ys[sorted_inds]]

    return sorted_angles, sorted_pos


def get_all_tris(ids):
    perms = list(itertools.combinations(ids, 3))
    return perms



def match_angles(angles1, angles2):
    # get first two angles of each list
    #  angles are sorted, so this is smallest 2 angles
    angles1 = np.array(angles1)[:,:2]
    angles2 = np.array(angles2)[:,:2]

    tree_angles1 = KDTree(angles1)
    tree_angles2 = KDTree(angles2)

    dists, inds = tree_angles2.query(angles1, k=1)

    return dists, inds



def get_all_angles(xs, ys, N=4):
    allperms = set()
    for ii in range(len(xs)):
        dists = (xs-xs[ii])**2 + (ys-ys[ii])**2
        closest = np.argsort(dists).tolist()[:N+1]

        perms = [tuple(sorted(p)) for p in get_all_tris(closest)]
        for p in perms:
            allperms.add(p)

    allperms = list(allperms)
    angles = []
    pos = []
    for p in allperms:
        sorted_angles, sorted_pos = get_angles(xs[list(p)], ys[list(p)])
        angles.append(sorted_angles)
        pos.append(sorted_pos)

    return angles, pos



def get_frame_transform(ref_fname, target_fname, ref_data = None, target_data = None):
    if ref_data is not None:
        xs, ys, img1 = ref_data
    else:
        xs, ys, img1 = get_star_locs(load_image(ref_fname), return_image=True)

    if target_data is not None:
        xs_shift, ys_shift, img2 = target_data
    else:
        xs_shift, ys_shift, img2 = get_star_locs(load_image(target_fname), return_image=True)


    if xs_shift is None:
        return None, None, None, None, None, None

#    print("COMARING IMAGE SHAPES:", np.shape(img2), np.shape(img1))
#    ref_shape = np.shape(img1)
#    tar_shape = np.shape(img2)
#    shape_diff = np.array(ref_shape)-np.array(tar_shape)
#    print(shape_diff)
#
#    img2 = cv.copyMakeBorder(img2, 0, shape_diff[0], 0, shape_diff[1],
#                             cv.BORDER_CONSTANT)
#

    starttime = time.time()
    angles, pos = get_all_angles(xs, ys)
    angles_shift, pos_shift = get_all_angles(xs_shift, ys_shift)

    dists, inds = match_angles(angles, angles_shift)
    weights = np.pow(np.clip(1-dists*10, 0, 1), 4)

    all_refs = []
    all_targs = []


    for ii, ind in enumerate(inds):
        w = weights[ii][0]
        ind = ind[0]
        p = pos[ii]
        ps = pos_shift[ind]

        ref_point  = [p[0][0] , p[1][0]]
        targ_point = [ps[0][0], ps[1][0]]

        if ref_point not in all_refs:
            all_refs.append(ref_point)
            all_targs.append(targ_point)


    target_star_pos = np.vstack((xs_shift, ys_shift)).T
#    target_star_pos_3d =np.vstack((target_star_pos, np.zeros_like(xs_shift))).T
    ref_star_pos = np.vstack((xs, ys)).T
#    ref_star_pos_3d =np.vstack((ref_star_pos, np.zeros_like(xs))).T
#
#
#    src_cloud = cv.ppf_match_3d.Mat(ref_star_pos_3d)
#          
#    print("B", np.shape(target_star_pos_3d))
#
#    print("D", np.shape(ref_star_pos_3d))




    # estimate transformation matrix here
    N = 80
    print(np.shape(target_star_pos))
    print(np.shape(ref_star_pos))

    #H3, inpts = cv.estimateAffinePartial2D(np.array(target_star_pos),
    #                                        np.array(ref_star_pos)[:96],
    #                                   ransacReprojThreshold=0.1)

    H2, mask = cv.findHomography(np.array(target_star_pos),
                                            np.array(ref_star_pos)[:96],
                                       cv.RANSAC, 5.0)
    inpts2 = mask
    print(mask)
    
    print("HERE" , np.sum(mask))
    print("HERE again " , np.sum(inpts2))

#    M, mask = cv.findHomography(ref_star_pos, target_star_pos, cv.RANSAC, 5.0)

    H, inpts = cv.estimateAffinePartial2D(np.array(all_targs),
                                        np.array(all_refs),
                                       ransacReprojThreshold=5.0)

    print(H)

    objpoints = []
    imgpoints = []

    for ii, ref_pt, targ_pt in zip(inpts, all_refs, all_targs):
        if np.sum(ii) == 1:
#            objpoints.append([*ref_pt, 0])
#            imgpoints.append([*targ_pt, 0])

            objpoints.append(ref_pt)
            imgpoints.append(targ_pt)

#    w, h = np.shape(img2)
#    warped_img = cv.warpPerspective(img2, H2, (w, h))

    print(objpoints)
    #ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, img2.shape[::-1], None, None)
#    val = cv.getPerspectiveTransform(np.array(objpoints),np.array(imgpoints))

#    rotation_part = H[:2, :2]
#    translation_part = H[:2, 2]
#
#    # Calculate the current scale (determinant of rotation matrix is scale²)
#    current_scale = np.sqrt(np.abs(np.linalg.det(rotation_part)))
#
#    # Normalize the rotation matrix to have scale=1.0
#    normalized_rotation = rotation_part * current_scale
#
#    # Create the new transformation matrix with scale=1.0
#    new_transform = np.zeros((2, 3), dtype=np.float32)
#    new_transform[:2, :2] = normalized_rotation
#    new_transform[:2, 2] = translation_part

    print(H)

    fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True) 
    axs[0].imshow(img1, origin='lower')

    for inlier, pt in zip(inpts, all_refs):
        if np.sum(inlier) == 1:
            axs[0].scatter(pt[0], pt[1], color='white', facecolor='none', linewidth=2)
        else:
            axs[0].scatter(pt[0], pt[1], color='grey', facecolor='none', linewidth=1)


    for inlier, pt in zip(inpts2, ref_star_pos[:94]):
        if np.sum(inlier) == 1:
            axs[0].scatter(pt[0], pt[1], color='cyan',s=8, facecolor='none', linewidth=2)
        else:
            axs[0].scatter(pt[0], pt[1], color='yellow', s=8,facecolor='none', linewidth=1)


#    H = new_transform


    axs[1].imshow(img2, origin='lower')
    for inlier, pt in zip(inpts, all_targs):
        if np.sum(inlier) == 1:
            axs[1].scatter(pt[0], pt[1], color='white', facecolor='none', linewidth=2)
        else:
            axs[1].scatter(pt[0], pt[1], color='grey', facecolor='none', linewidth=1)

    for inlier, pt in zip(inpts2, target_star_pos):
        if np.sum(inlier) == 1:
            axs[1].scatter(pt[0], pt[1], color='cyan',s=8, facecolor='none', linewidth=2)
        else:
            axs[1].scatter(pt[0], pt[1], color='yellow',s=8, facecolor='none', linewidth=1)



    plt.show()
#    H = new_transform

    translation_xdir = np.sign(H[0][-1])
    translation_ydir = np.sign(H[1][-1])

    translation_x = int(round(np.abs(H[0][-1])))
    translation_y = int(round(np.abs(H[1][-1])))
    rot_angle = np.arcsin(H[1][0])

    # if rotation is positive
    if rot_angle > 0:
        shiftx = translation_x# + int(H[1][0] * np.shape(img2)[0])+1
    else: 
        shiftx = translation_x

    # if rotation is negative
    if rot_angle < 0 or rot_angle > np.pi/2:
        shifty = translation_y# + int(H[1][0] * np.shape(img2)[0])+1
    else:
        shifty = translation_y

    # transform the points here

    temp = img2.copy()
    
    # top bottom left right
    # if shiftx is negative, pad top

    if translation_xdir < 0:
        horizontal_shift = (shiftx, 0)
    else:
        horizontal_shift = (0, max((shiftx-1, 0)))
    if translation_ydir < 0:
        vertical_shift = (shifty, 0)
    else:
        vertical_shift = (0, max((shifty-1, 0)))


#    horizontal_shift = (shiftx, 0)
#    vertical_shift = (shifty, 0)

    total_shift = [vertical_shift[0], vertical_shift[1],
                   horizontal_shift[0], horizontal_shift[1]]

    
    img_border = cv.copyMakeBorder(np.ones_like(img2, dtype=float), *total_shift,
                             cv.BORDER_CONSTANT)

    temp = cv.copyMakeBorder(temp, *total_shift,
                             cv.BORDER_CONSTANT)
    outshape = (np.shape(temp)[1], np.shape(temp)[0])

    try:
        transformed1 = cv.warpAffine(temp, H, outshape)
        img_border= cv.warpAffine(img_border, H, outshape)
    except:
        return None, None, total_shift, xs_shift, ys_shift, img2

    return transformed1, img_border, total_shift, xs_shift, ys_shift, img2


if __name__ == "__main__":
    starttime = time.time()
    fnames = ["/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_2000.FIT",
              "/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_2075.FIT"]
    fnames = []
    for ii in range(10000)[990:2120:50]:
        fnames.append(f"/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_{ii:04d}.FIT")

    #mtx, dist, newcameramtx, roi = load_distortion_params()
    #img = load_image(fname, preprocess=False, border_percent=0)
    #dst = correct_distortion(img, mtx, dist, newcameramtx, roi)
#    fnames = [] 
#    for ii in range(10000)[6260:7260:2]:
#        fnames.append(f"/Users/michael/Pictures/sky_apr23-2025/DSC0{ii:04d}.ARW")


#    fnames = fnames[::-1]
#    fnames = []
#    for ii in range(10000)[800:900]:
#        fnames.append(f"/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_{ii:04d}.FIT")


    fnames = ["/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_2000.FIT",
              "/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_2200.FIT"]
#              "/Users/michael/ASICAP/CapObj/2025-04-17_03_46_06Z/2025-04-17-0346_1-CapObj_2200.FIT"]



    ref_fname = fnames[0]
    ref_xs, ref_ys, ref_image = get_star_locs(load_image(ref_fname), return_image=True)
    first_image = ref_image.copy()
    final_image = ref_image.copy().astype(np.float64)
    Nimages = np.ones_like(final_image)
    total_shift = np.array([0,0,0,0])
    total_shift_inv = np.array([0,0,0,0])

    shifts = []

    ii = 0

    for target_fname in tqdm(fnames[1:]):
        print("STARTING ", target_fname)
        final_image_orig = final_image.copy()
        Nimages_orig = Nimages.copy()

        transformed, img_contribution, shift, tar_xs, tar_ys, tar_image = get_frame_transform(ref_fname, target_fname,
                                          ref_data = (ref_xs, ref_ys, ref_image))
        if transformed is None:
            continue

        if np.sum(shift) > 500:
            print("TOO LARGE OF SHIFT, SKIPPING")
            continue

        if len(shifts) > 5:
            if np.sum(shift) > 10*np.std(shifts):
                print("FRAME SHIFT OUTLIER:", shift, np.sum(shift), 5*np.std(shifts))
#                continue

        shifts.append(np.sum(shift))
        print(shift)
        print(total_shift_inv)

        # transformed is in correct place here
        # compare size of final image and transformed image
        transformed_size = np.shape(transformed)
        final_size = np.shape(final_image)
        print("TRANSFORMED IS IN PLACE HERE")
        print("FINAL SHAPE: ", final_size, "NEW IMAGE SHAPE: ", transformed_size)
        ydiff = np.abs(final_size[0]-transformed_size[0])
        xdiff = np.abs(final_size[1]-transformed_size[1])
        print("SIZE OFFSET IS ", xdiff, ydiff)



        # for y shift
        if shift[0] == 0 and shift[1] > 0:

            #if transformed is smaller than final image
            if transformed_size[0] < final_size[0]:
                transformed = cv.copyMakeBorder(transformed, 0,ydiff,0,0, cv.BORDER_CONSTANT)

            #if final image is smaller than transformed 
            else:
                final_image = cv.copyMakeBorder(final_image, 0,ydiff,0,0, cv.BORDER_CONSTANT)
                Nimages = cv.copyMakeBorder(Nimages, 0,ydiff,0,0, cv.BORDER_CONSTANT)
            print("adding to bottom")

        else:
            print("adding to top")
            transformed = cv.copyMakeBorder(transformed, *[total_shift_inv[0], total_shift_inv[1], 0, 0], cv.BORDER_CONSTANT)
            img_contribution = cv.copyMakeBorder(img_contribution, *[total_shift_inv[0], total_shift_inv[1], 0, 0], cv.BORDER_CONSTANT)

            final_image = cv.copyMakeBorder(final_image, *[shift[0], shift[1], 0, 0], cv.BORDER_CONSTANT)
            Nimages = cv.copyMakeBorder(Nimages, *[shift[0], shift[1], 0, 0], cv.BORDER_CONSTANT)

        # for x shift
        if shift[2] == 0 and shift[3] > 0: # reverse
            #if transformed is smaller than final image
            if transformed_size[1] < final_size[1]:
                transformed = cv.copyMakeBorder(transformed, 0,0,0,xdiff, cv.BORDER_CONSTANT)  

            # if final image is smaller than transform
            else:
                final_image = cv.copyMakeBorder(final_image, 0,0,0,xdiff, cv.BORDER_CONSTANT)
                Nimages = cv.copyMakeBorder(Nimages, 0,0,0,xdiff, cv.BORDER_CONSTANT)
            print("adding to right")

        else:
    #        final_image = cv.copyMakeBorder(final_image, 0,0,xdiff,0, cv.BORDER_CONSTANT)
    #        Nimages = cv.copyMakeBorder(Nimages, 0,0,xdiff,0, cv.BORDER_CONSTANT)
            print("adding to left")
            transformed      = cv.copyMakeBorder(transformed, *[0,0,total_shift_inv[2], total_shift_inv[3]], cv.BORDER_CONSTANT)
            img_contribution = cv.copyMakeBorder(img_contribution, *[0,0,total_shift_inv[2], total_shift_inv[3]],cv.BORDER_CONSTANT)
            final_image      = cv.copyMakeBorder(final_image, *[0,0,shift[2], shift[3]], cv.BORDER_CONSTANT)
            Nimages          = cv.copyMakeBorder(Nimages, *[0,0,shift[2], shift[3]], cv.BORDER_CONSTANT)






        # here is the comparison
        plot=True
        if plot:
            fig, axs = plt.subplots(1, 4, figsize=(14, 4), sharex=True, sharey=True)
            scaler = ZScaleInterval()
            limits = scaler.get_limits(final_image)
            axs[0].imshow(final_image, origin='lower', vmin=limits[0], vmax=limits[1])
            limits = scaler.get_limits(transformed)
            axs[1].imshow(transformed, origin='lower', vmin=limits[0], vmax=limits[1])

        try:
            final_image += transformed
            print("Added transformed to image")
            Nimages += img_contribution
            print("Added contribution to Nimages")
        except ValueError as e:
            print("Encountered error: ", e)
            final_image = final_image_orig.copy()
            Nimages = Nimages_orig.copy()
            continue

        if plot:
            scaler = ZScaleInterval()
#            limits = scaler.get_limits(np.nan_to_num(final_image/Nimages))
            axs[2].imshow(np.nan_to_num(Nimages), origin='lower', aspect='auto', vmin=0, vmax=ii)#, vmin=limits[0], vmax=limits[1])
            axs[3].imshow(img_contribution, origin='lower', aspect='auto', vmin=0, vmax=1)#, vmin=limits[0], vmax=limits[1])

            plt.show()



        total_shift += np.array(shift)

        total_shift_inv = np.array([total_shift[1], total_shift[0],
                                    total_shift[3], total_shift[2]])


        ref_xs, ref_ys, ref_image = get_star_locs(np.nan_to_num(final_image/Nimages), return_image=True)
        ii += 1


    fig, axs = plt.subplots(1, 3, figsize=(12, 4), sharex=True, sharey=True)


    scaler = ZScaleInterval()
    transformed -= np.min(transformed)
    limits = scaler.get_limits(transformed)
    axs[0].imshow(transformed, vmin=limits[0], vmax=limits[1], cmap='Greys_r', origin='lower')

    Nimages[Nimages==0] = np.inf
    final_image = np.nan_to_num(final_image/Nimages)
    final_image = final_image-np.min(final_image)
#    print(np.min(final_image), np.max(final_image))
    limits = scaler.get_limits(final_image)
    print(limits)
    axs[1].imshow(final_image, vmin=limits[0], vmax=limits[1], cmap='Greys_r', origin='lower')
    axs[2].imshow(Nimages, origin='lower')
    fig.tight_layout()
#    hdul = fits.HDUList()
#    hdul.append(fits.PrimaryHDU())
#    hdul.append()
#    hdul.writeto("output_2000.fits", overwrite=True)

    hdu = fits.open(ref_fname)
    print(hdu[0].data)

    #fitsimg = fits.ImageHDU(data=final_image)
    hdu[0].data = final_image
#    hdu.writeto("output_2200.fits", overwrite=True)
    plt.show()
    
