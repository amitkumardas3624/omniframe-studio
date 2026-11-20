#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace {

struct Color {
    std::uint8_t r{0};
    std::uint8_t g{0};
    std::uint8_t b{0};
    std::uint8_t a{255};
};

Color parse_color(const std::string& raw) {
    std::string value = raw;
    if (!value.empty() && value.front() == '#') {
        value.erase(value.begin());
    }
    if (value.size() == 3) {
        std::string expanded;
        for (char ch : value) {
            expanded.push_back(ch);
            expanded.push_back(ch);
        }
        value = expanded + "FF";
    } else if (value.size() == 6) {
        value += "FF";
    }
    if (value.size() != 8) {
        return {};
    }
    auto component = [&value](std::size_t offset) -> std::uint8_t {
        try {
            return static_cast<std::uint8_t>(std::stoul(value.substr(offset, 2), nullptr, 16));
        } catch (...) {
            return 0;
        }
    };
    return {component(0), component(2), component(4), component(6)};
}

void blend_pixel(std::uint8_t* destination, const Color& source) {
    const float source_alpha = static_cast<float>(source.a) / 255.0F;
    const float destination_alpha = static_cast<float>(destination[3]) / 255.0F;
    const float output_alpha = source_alpha + destination_alpha * (1.0F - source_alpha);
    if (output_alpha <= 0.0F) {
        return;
    }
    for (int channel = 0; channel < 3; ++channel) {
        const float src = static_cast<float>(reinterpret_cast<const std::uint8_t*>(&source)[channel]) / 255.0F;
        const float dst = static_cast<float>(destination[channel]) / 255.0F;
        destination[channel] = static_cast<std::uint8_t>(
            std::clamp((src * source_alpha + dst * destination_alpha * (1.0F - source_alpha)) /
                           output_alpha * 255.0F,
                       0.0F, 255.0F));
    }
    destination[3] = static_cast<std::uint8_t>(std::clamp(output_alpha * 255.0F, 0.0F, 255.0F));
}

}  // namespace

class FramePipeSink {
public:
    FramePipeSink(const std::string& output_dir, double fps, int width, int height, int start_frame = 0)
        : output_dir_(output_dir), fps_(fps), width_(width), height_(height), frame_index_(start_frame) {
        if (fps_ <= 0.0 || width_ <= 0 || height_ <= 0) {
            throw std::invalid_argument("fps, width, and height must be positive");
        }
        fs::create_directories(output_dir_);
    }

    void write_rgba(py::bytes frame_bytes, int width, int height) {
        if (closed_) {
            throw std::runtime_error("FramePipeSink is already closed");
        }
        if (width != width_ || height != height_) {
            throw std::invalid_argument("frame dimensions do not match sink");
        }
        std::string payload = frame_bytes;
        const std::size_t expected = static_cast<std::size_t>(width_) * height_ * 4U;
        if (payload.size() != expected) {
            throw std::invalid_argument("RGBA frame has an unexpected byte length");
        }
        const fs::path target = fs::path(output_dir_) / ("frame_" + number(frame_index_) + ".rgba");
        {
            py::gil_scoped_release release;
            std::ofstream stream(target, std::ios::binary);
            if (!stream) {
                throw std::runtime_error("could not open native frame output");
            }
            stream.write(payload.data(), static_cast<std::streamsize>(payload.size()));
            if (!stream) {
                throw std::runtime_error("could not write native frame output");
            }
        }
        ++frame_index_;
    }

    void close() { closed_ = true; }
    int frame_count() const { return frame_index_; }

private:
    static std::string number(int value) {
        char buffer[32];
        std::snprintf(buffer, sizeof(buffer), "%06d", value);
        return buffer;
    }

    std::string output_dir_;
    double fps_;
    int width_;
    int height_;
    int frame_index_;
    bool closed_{false};
};

class CartoonRasterizer {
public:
    py::bytes render_rgba(int width, int height, const py::list& layers, int /*frame*/ = 0) const {
        if (width <= 0 || height <= 0) {
            throw std::invalid_argument("width and height must be positive");
        }
        std::vector<std::uint8_t> pixels(static_cast<std::size_t>(width) * height * 4U, 0);
        for (const py::handle& handle : layers) {
            const py::dict layer = py::reinterpret_borrow<py::dict>(handle);
            const std::string kind = py::str(layer[py::str("kind")]);
            if (kind != "solid" && kind != "vector") {
                throw py::value_error("unsupported native cartoon layer: " + kind);
            }
            const std::string color_text = layer.contains("color") ? py::str(layer[py::str("color")]) : "#000000";
            Color color = parse_color(color_text);
            const double opacity = layer.contains("opacity") ? py::float_(layer[py::str("opacity")]) : 1.0;
            color.a = static_cast<std::uint8_t>(std::clamp(opacity, 0.0, 1.0) * color.a);
            const int center_x = layer.contains("x") ? py::int_(layer[py::str("x")]) : 0;
            const int center_y = layer.contains("y") ? py::int_(layer[py::str("y")]) : 0;
            const int radius = kind == "vector" ? 50 : 50;
            for (int y = std::max(0, center_y - radius); y < std::min(height, center_y + radius); ++y) {
                for (int x = std::max(0, center_x - radius); x < std::min(width, center_x + radius); ++x) {
                    if (kind == "vector") {
                        const int dx = x - center_x;
                        const int dy = y - center_y;
                        if (dx * dx + dy * dy > radius * radius) {
                            continue;
                        }
                    }
                    auto* destination = pixels.data() + (static_cast<std::size_t>(y) * width + x) * 4U;
                    blend_pixel(destination, color);
                }
            }
        }
        return py::bytes(reinterpret_cast<const char*>(pixels.data()), pixels.size());
    }
};

PYBIND11_MODULE(_omniframe_native, module) {
    module.doc() = "Optional OmniFrame Studio C++17 accelerator";
    module.def("native_available", []() { return true; });
    py::class_<FramePipeSink>(module, "FramePipeSink")
        .def(py::init<const std::string&, double, int, int, int>(), py::arg("output_dir"), py::arg("fps"),
             py::arg("width"), py::arg("height"), py::arg("start_frame") = 0)
        .def("write_rgba", &FramePipeSink::write_rgba, py::arg("frame_bytes"), py::arg("width"), py::arg("height"))
        .def("close", &FramePipeSink::close)
        .def_property_readonly("frame_count", &FramePipeSink::frame_count);
    py::class_<CartoonRasterizer>(module, "CartoonRasterizer")
        .def(py::init<>())
        .def("render_rgba", &CartoonRasterizer::render_rgba, py::arg("width"), py::arg("height"),
             py::arg("layers"), py::arg("frame") = 0);
}
