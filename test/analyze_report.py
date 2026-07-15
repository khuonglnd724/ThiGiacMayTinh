import json

with open('test/output/evaluation_report.json', 'r') as f:
    data = json.load(f)
    
print('=== OVERALL MODEL PERFORMANCE ===')
print(f'Box mAP50: {data["ultralytics_metrics"]["box_map50"]:.4f}')
print(f'Box mAP50-95: {data["ultralytics_metrics"]["box_map50_95"]:.4f}')
print(f'Mask mAP50: {data["ultralytics_metrics"]["mask_map50"]:.4f}')
print(f'Mask mAP50-95: {data["ultralytics_metrics"]["mask_map50_95"]:.4f}')
print(f'Box Precision: {data["ultralytics_metrics"]["box_precision"]:.4f}')
print(f'Box Recall: {data["ultralytics_metrics"]["box_recall"]:.4f}')
print(f'Mask Precision: {data["ultralytics_metrics"]["mask_precision"]:.4f}')
print(f'Mask Recall: {data["ultralytics_metrics"]["mask_recall"]:.4f}')
print()

print('=== CUSTOM GLOBAL METRICS ===')
cg = data['custom_metrics']['global']
print(f'Total Samples: {cg["total_samples"]}')
print(f'TP: {cg["tp"]}, FP: {cg["fp"]}, FN: {cg["fn"]}')
print(f'Precision: {cg["precision"]:.4f}')
print(f'Recall: {cg["recall"]:.4f}')
print(f'F1-Score: {cg["f1_score"]:.4f}')
print(f'Mean IoU: {cg["mean_iou"]:.4f}')
print(f'Mean Dice: {cg["mean_dice"]:.4f}')
print()

print('=== PER-CLASS ANALYSIS ===')
print(f'{"Class":<15} {"Samples":<8} {"Prec":<7} {"Rec":<7} {"F1":<7} {"IoU":<7} {"Dice":<7}')
print('-' * 58)
for c in data['custom_metrics']['per_class']:
    print(f'{c["class"]:<15} {c["samples"]:<8} {c["precision"]:<7.4f} {c["recall"]:<7.4f} {c["f1_score"]:<7.4f} {c["mean_iou"]:<7.4f} {c["mean_dice"]:<7.4f}')
print()

# Worst classes by recall
print('=== UNDERPERFORMING CLASSES (< 0.85 recall) ===')
for c in sorted(data['custom_metrics']['per_class'], key=lambda x: x['recall']):
    if c['recall'] < 0.85:
        print(f'{c["class"]:<15} Recall={c["recall"]:.4f} IoU={c["mean_iou"]:.4f} F1={c["f1_score"]:.4f} (FN={c["fn"]})')

print()
print('=== BEST PERFORMING CLASSES (>= 0.95 recall) ===')
for c in sorted(data['custom_metrics']['per_class'], key=lambda x: -x['recall']):
    if c['recall'] >= 0.95:
        print(f'{c["class"]:<15} Recall={c["recall"]:.4f} IoU={c["mean_iou"]:.4f} F1={c["f1_score"]:.4f}')