#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>

namespace {

constexpr int kPalette[4][3] = {
    {0, 0, 0},
    {255, 255, 255},
    {232, 176, 0},
    {200, 0, 0},
};

constexpr int kKernel[6][3] = {
    {1, 0, 1},
    {2, 0, 1},
    {-1, 1, 1},
    {0, 1, 1},
    {1, 1, 1},
    {0, 2, 1},
};

void set_error(char* error, int error_len, const char* message) {
    if (!error || error_len <= 0) {
        return;
    }
    std::strncpy(error, message, static_cast<std::size_t>(error_len - 1));
    error[error_len - 1] = '\0';
}

double clamp_byte(double value) {
    return std::max(0.0, std::min(255.0, value));
}

int nearest_index(const double* pixel, const int* allowed, int allowed_count) {
    int best = allowed[0];
    double best_dist = 1e30;
    for (int i = 0; i < allowed_count; ++i) {
        int idx = allowed[i];
        double dr = pixel[0] - kPalette[idx][0];
        double dg = pixel[1] - kPalette[idx][1];
        double db = pixel[2] - kPalette[idx][2];
        double dist = dr * dr + dg * dg + db * db;
        if (dist < best_dist) {
            best_dist = dist;
            best = idx;
        }
    }
    return best;
}

}  // namespace

extern "C" int inksight_atkinson_palette(
    const std::uint8_t* rgb,
    int width,
    int height,
    int colors,
    std::uint8_t* out,
    char* error,
    int error_len
) {
    if (!rgb || !out) {
        set_error(error, error_len, "null input/output pointer");
        return 1;
    }
    if (width <= 0 || height <= 0) {
        set_error(error, error_len, "invalid dimensions");
        return 2;
    }
    if (colors != 3 && colors != 4) {
        set_error(error, error_len, "colors must be 3 or 4");
        return 3;
    }

    const int allowed_3[] = {0, 1, 3};
    const int allowed_4[] = {0, 1, 2, 3};
    const int* allowed = colors == 3 ? allowed_3 : allowed_4;
    const int allowed_count = colors == 3 ? 3 : 4;

    const int pixel_count = width * height;
    std::vector<double> data(static_cast<std::size_t>(pixel_count) * 3);
    for (int i = 0; i < pixel_count * 3; ++i) {
        data[static_cast<std::size_t>(i)] = static_cast<double>(rgb[i]);
    }

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int pos = y * width + x;
            const int base = pos * 3;
            double old_pixel[3] = {data[base], data[base + 1], data[base + 2]};
            int idx = nearest_index(old_pixel, allowed, allowed_count);
            out[pos] = static_cast<std::uint8_t>(idx);

            double err[3] = {
                old_pixel[0] - kPalette[idx][0],
                old_pixel[1] - kPalette[idx][1],
                old_pixel[2] - kPalette[idx][2],
            };

            for (const auto& step : kKernel) {
                const int nx = x + step[0];
                const int ny = y + step[1];
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
                    continue;
                }
                const int nbase = (ny * width + nx) * 3;
                for (int channel = 0; channel < 3; ++channel) {
                    data[nbase + channel] = clamp_byte(
                        data[nbase + channel] + err[channel] * (static_cast<double>(step[2]) / 8.0)
                    );
                }
            }
        }
    }

    return 0;
}

extern "C" int inksight_atkinson_bw(
    const std::uint8_t* gray,
    int width,
    int height,
    std::uint8_t* out,
    char* error,
    int error_len
) {
    if (!gray || !out) {
        set_error(error, error_len, "null input/output pointer");
        return 1;
    }
    if (width <= 0 || height <= 0) {
        set_error(error, error_len, "invalid dimensions");
        return 2;
    }

    const int pixel_count = width * height;
    std::vector<double> data(static_cast<std::size_t>(pixel_count));
    for (int i = 0; i < pixel_count; ++i) {
        data[static_cast<std::size_t>(i)] = static_cast<double>(gray[i]);
    }

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int pos = y * width + x;
            const double old_value = data[pos];
            const double new_value = old_value >= 128.0 ? 255.0 : 0.0;
            out[pos] = static_cast<std::uint8_t>(new_value);
            const double err = old_value - new_value;

            for (const auto& step : kKernel) {
                const int nx = x + step[0];
                const int ny = y + step[1];
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
                    continue;
                }
                const int npos = ny * width + nx;
                data[npos] = clamp_byte(data[npos] + err * (static_cast<double>(step[2]) / 8.0));
            }
        }
    }

    return 0;
}
