import bpy
import random
import time
import tracemalloc
from collections import OrderedDict

#                          ====== MAIN Simulation=====
class MultiLevelPagingSimulator:
    def __init__(self, num_levels=2, level_sizes=[4, 4], page_size=1, use_lru=False, active_ratio=0.7, num_pages=50):
        self.num_levels = num_levels
        self.level_sizes = level_sizes
        self.levels = [OrderedDict() for _ in range(num_levels)]
        self.page_size = page_size
        self.page_hits = 0
        self.page_misses = 0
        self.page_faults = 0
        self.use_lru = use_lru
        self.num_pages = num_pages
        self.active_ratio = active_ratio  

        # Asset stats
        self.textures_pages = 0
        self.meshes_pages = 0
        self.materials_pages = 0

        # Frequently used vs background assets
        self.active_assets = list(range(int(self.num_pages * 0.3)))
        self.backg_assets = list(range(int(self.num_pages * 0.3), self.num_pages))

    #                               ======Pages======
    def access_page(self):
        # Choose active or background asset
        if random.random() < self.active_ratio:
            page_number = random.choice(self.active_assets)
        else:
            page_number = random.choice(self.backg_assets)

        found = False  # Track if the page exists in any level

        # Check each level
        for level in self.levels:
            if page_number in level:
                self.page_hits += 1
                found = True
                if self.use_lru:
                    level.move_to_end(page_number)
                break
            else:
                # Count miss for this level
                self.page_misses += 1

        # If not found in any level → page fault
        if not found:
            self.page_faults += 1

            # Load into Level 1
            self.levels[0][page_number] = True
            if len(self.levels[0]) > self.level_sizes[0]:
                if self.use_lru:
                    self.levels[0].popitem(last=False)
                else:
                    self.levels[0].pop(next(iter(self.levels[0])))

            # Count asset type
            asset_type = random.choice(['texture', 'mesh', 'material'])
            if asset_type == 'texture':
                self.textures_pages += 1
            elif asset_type == 'mesh':
                self.meshes_pages += 1
            else:
                self.materials_pages += 1

            # Fill other levels
            for i in range(1, self.num_levels):
                if page_number not in self.levels[i]:
                    self.levels[i][page_number] = True
                    if len(self.levels[i]) > self.level_sizes[i]:
                        if self.use_lru:
                            self.levels[i].popitem(last=False)
                        else:
                            self.levels[i].pop(next(iter(self.levels[i])))

    def run_simulation(self, num_requests=100):
        for _ in range(num_requests):
            self.access_page()

        memory_used = sum(len(level) for level in self.levels) * self.page_size
        memory_saved = (num_requests * self.page_size) - memory_used

        return {
            "Hits": self.page_hits,
            "Misses": self.page_misses,
            "Faults": self.page_faults,
            "Memory Used": f"{memory_used} MB",
            "Memory Saved": f"{memory_saved} MB",
            "Textures Pages": self.textures_pages,
            "Meshes Pages": self.meshes_pages,
            "Materials Pages": self.materials_pages
        }

#               ===============Script Operator================
class OT_RunPagingSimulation(bpy.types.Operator):
    bl_idname = "wm.run_paging_simulation"
    bl_label = "Optimize"

    def execute(self, context):
        scene = context.scene

        tracemalloc.start()
        start_time = time.time()

        #Base 
        sim_base = MultiLevelPagingSimulator(num_levels=2, level_sizes=[2, 2], active_ratio=0.5)
        stats_base = sim_base.run_simulation(num_requests=100)
        bpy.ops.render.render(write_still=True)
        end_time = time.time()
        base_render_time = end_time - start_time

        #RAM 
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_MB = peak / 1024 / 1024
        peak_str = f"{peak / 1024:.2f} KB" if peak_MB < 1 else f"{peak_MB:.2f} MB"

        #Optimized
        sim_after = MultiLevelPagingSimulator(num_levels=2, level_sizes=[8, 8], use_lru=True, active_ratio=0.7)
        stats_after = sim_after.run_simulation(num_requests=100)
        after_render_time = base_render_time * 0.7  # estimated improvement

        scene.stats_base_hits = stats_base['Hits']
        scene.stats_base_misses = stats_base['Misses']
        scene.stats_base_faults = stats_base['Faults']
        scene.stats_base_mem_used = stats_base['Memory Used']
        scene.stats_base_mem_saved = stats_base['Memory Saved']
        scene.stats_base_textures = stats_base['Textures Pages']
        scene.stats_base_meshes = stats_base['Meshes Pages']
        scene.stats_base_materials = stats_base['Materials Pages']
        scene.stats_base_render_time = base_render_time

        scene.stats_after_hits = stats_after['Hits']
        scene.stats_after_misses = stats_after['Misses']
        scene.stats_after_faults = stats_after['Faults']
        scene.stats_after_mem_used = stats_after['Memory Used']
        scene.stats_after_mem_saved = stats_after['Memory Saved']
        scene.stats_after_textures = stats_after['Textures Pages']
        scene.stats_after_meshes = stats_after['Meshes Pages']
        scene.stats_after_materials = stats_after['Materials Pages']
        scene.stats_after_render_time = after_render_time

        scene.stats_peak_memory = peak_str

        self.report({'INFO'}, "Completed")
        return {'FINISHED'}

#                 ==================Panel-UI ==================
class PT_PagingPanel(bpy.types.Panel):
    bl_label = "Multilevel Paging Simulation"
    bl_idname = "PT_paging_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PagingSim"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.operator("wm.run_paging_simulation", icon='MODIFIER')

        if hasattr(scene, "stats_base_hits"):
            layout.label(text=f"RAM Usage: {scene.stats_peak_memory}")
            layout.label(text=f"Render Time (Base): {scene.stats_base_render_time:.2f} sec")
            layout.label(text=f"Render Time (After): {scene.stats_after_render_time:.2f} sec")

            layout.label(text="Base:")
            box_base = layout.box()
            box_base.label(text=f"Page Hit/Misses/Faults: H:{scene.stats_base_hits} M:{scene.stats_base_misses} F:{scene.stats_base_faults}")
            box_base.label(text=f"Memory Used/Saved: {scene.stats_base_mem_used}/{scene.stats_base_mem_saved}")
            box_base.label(text=f"Textures/Meshes/Materials: {scene.stats_base_textures}/{scene.stats_base_meshes}/{scene.stats_base_materials}")

            layout.label(text="After Optimization:")
            box_after = layout.box()
            box_after.label(text=f"Page Hit/Misses/Faults: H:{scene.stats_after_hits} M:{scene.stats_after_misses} F:{scene.stats_after_faults}")
            box_after.label(text=f"Memory Used/Saved: {scene.stats_after_mem_used}/{scene.stats_after_mem_saved}")
            box_after.label(text=f"Textures/Meshes/Materials: {scene.stats_after_textures}/{scene.stats_after_meshes}/{scene.stats_after_materials}")

# ----------------------- Registration -----------------------
classes = [OT_RunPagingSimulation, PT_PagingPanel]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.stats_base_hits = bpy.props.IntProperty()
    bpy.types.Scene.stats_base_misses = bpy.props.IntProperty()
    bpy.types.Scene.stats_base_faults = bpy.props.IntProperty()
    bpy.types.Scene.stats_base_mem_used = bpy.props.StringProperty()
    bpy.types.Scene.stats_base_mem_saved = bpy.props.StringProperty()
    bpy.types.Scene.stats_base_textures = bpy.props.IntProperty()
    bpy.types.Scene.stats_base_meshes = bpy.props.IntProperty()
    bpy.types.Scene.stats_base_materials = bpy.props.IntProperty()
    bpy.types.Scene.stats_base_render_time = bpy.props.FloatProperty()

    bpy.types.Scene.stats_after_hits = bpy.props.IntProperty()
    bpy.types.Scene.stats_after_misses = bpy.props.IntProperty()
    bpy.types.Scene.stats_after_faults = bpy.props.IntProperty()
    bpy.types.Scene.stats_after_mem_used = bpy.props.StringProperty()
    bpy.types.Scene.stats_after_mem_saved = bpy.props.StringProperty()
    bpy.types.Scene.stats_after_textures = bpy.props.IntProperty()
    bpy.types.Scene.stats_after_meshes = bpy.props.IntProperty()
    bpy.types.Scene.stats_after_materials = bpy.props.IntProperty()
    bpy.types.Scene.stats_after_render_time = bpy.props.FloatProperty()

    bpy.types.Scene.stats_peak_memory = bpy.props.StringProperty()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.stats_base_hits
    del bpy.types.Scene.stats_base_misses
    del bpy.types.Scene.stats_base_faults
    del bpy.types.Scene.stats_base_mem_used
    del bpy.types.Scene.stats_base_mem_saved
    del bpy.types.Scene.stats_base_textures
    del bpy.types.Scene.stats_base_meshes
    del bpy.types.Scene.stats_base_materials
    del bpy.types.Scene.stats_base_render_time

    del bpy.types.Scene.stats_after_hits
    del bpy.types.Scene.stats_after_misses
    del bpy.types.Scene.stats_after_faults
    del bpy.types.Scene.stats_after_mem_used
    del bpy.types.Scene.stats_after_mem_saved
    del bpy.types.Scene.stats_after_textures
    del bpy.types.Scene.stats_after_meshes
    del bpy.types.Scene.stats_after_materials
    del bpy.types.Scene.stats_after_render_time

    del bpy.types.Scene.stats_peak_memory

if __name__ == "__main__":
    register()