import numpy as np

from ml.subdivisions import grid_weights, imd_area_means, subdivision_table


def test_imd_area_means_are_cosine_weighted_and_ignore_nan():
    n = len(subdivision_table())
    lat = np.array([0.0, 60.0])
    assign = np.array([[0, 0], [0, 1]])
    rain = np.array([[[10.0, 10.0], [40.0, np.nan]]])  # one day
    out = imd_area_means(rain, assign, lat)
    assert out.shape == (1, n)
    w0, w60 = 1.0, np.cos(np.deg2rad(60))
    expect = (10 * w0 * 2 + 40 * w60) / (2 * w0 + w60)
    assert np.isclose(out[0, 0], expect)
    assert np.isnan(out[0, 1])  # only cell is missing
    assert np.isnan(out[0, 2])  # no cells at all


def test_grid_weights_rows_sum_to_one_and_map_to_nearest_cell():
    part = {
        "lat": np.array([10.0, 10.25]),
        "lon": np.array([70.0, 70.25]),
        "assign": np.array([[0, 0], [1, -1]]),
    }
    W = grid_weights(part, lat_f=np.array([9.0, 10.5]), lon_f=np.array([69.0, 70.5]))
    assert np.allclose(W[:2].sum(1), 1.0) and W[2:].sum() == 0
    field = np.array([[1.0, 2.0], [3.0, 4.0]])  # (lat_f, lon_f)
    # sub 0 cells: (10.0,70.0)->(10.5,70.5)=4 ; (10.0,70.25)->4 ; sub 1: (10.25,70.0)->4
    assert np.isclose(W[0] @ field.ravel(), 4.0)
